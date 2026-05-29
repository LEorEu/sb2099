# 设计：raw 降级为缓冲 + 引入「按日热梗表」daily_hot

- 日期：2026-05-29
- 状态：待评审
- 范围：sb2099 数据存储 / 保留策略重构（ingest + cron + web 读取层）

## 背景与动机

当前是「全量入库」：

- 每条弹幕无条件写入 `raw_danmaku`（一条一行，带 uid）。
- 每个不同的归一化内容 `content_norm` 立刻 upsert 进 `live_hot`，所以 `live_hot`
  本质是「见过的所有不同弹幕内容」，而非「热梗」。运行 2 天即 9.7 万行，无限增长。
- `recount_cron` 每分钟从 `raw_danmaku` 最近 7 天重算 `live_hot` 的
  `send_cnt_24h/7d`、`unique_sender_cnt_24h/7d`。
- `archive_cron` 04:00 删早于 `raw_retention_days`（默认 30）的 `raw_danmaku`。

问题：30 天保留 + 约 14.5 万条/天，`raw_danmaku` 稳态预估 1~1.5 GB；`live_hot`
无界增长。实际使用只关心「热梗榜」（每天 Top 10、每周 Top 50），不需要长期保留
原始明细，也不需要保留未达热度的内容。

## 目标

- 封住数据库增长上限（撑不爆），而非追求极致小。
- 只沉淀「真正的热梗」：单个数据日内被 **> 20 个不同 uid** 发过的内容。
- 今日榜实时（准实时）可见；保留最近 7 天供「本周榜」。
- 原始明细不长期保留。

非目标：

- 不追求跨天精确「unique 人数」（需 7 天明细，与瘦身冲突）；本周榜按累计发送量排。
- 不做严格逐条即时判定（每分钟~每小时一次的批量重算即可，延迟无感）。

## 核心概念

### 数据日（live_date）

一个数据日 = **当日 04:00 → 次日 04:00**。某条弹幕归属的数据日：

```
live_date = (ts - 4 小时).date()
```

与 04:00 的清理/边界对齐，凌晨 0–4 点的弹幕算前一个数据日。

### 阈值

`live_hot_min_unique_senders_24h`（已存在于 setting 表，默认 20）：单个数据日内
不同 uid 数 ≥ 该阈值，内容才算「热梗」并进入 `daily_hot`。降噪命中的内容
（`is_filtered`）不计入、不入表。

## 数据模型

### `raw_danmaku`（降级为当日缓冲）

结构不变。职责收窄为：仅为「N 个不同 uid」判定提供去重明细。

- 保留窗口 = **2 天**（保险，结算失败可重跑）。复用 `raw_retention_days`，默认值
  由 30 改为 2。
- 04:00 清理早于保留窗口的行。

### `daily_hot`（新表，沉淀层）

主键 `(live_date, content_norm)`。只装达标热梗，永不膨胀。

| 字段 | 类型 | 含义 |
|------|------|------|
| `live_date` | DATE | 数据日，如 `2026-05-29` |
| `content_norm` | TEXT | 归一化内容（主键之一） |
| `content_sample` | TEXT | 原样例（取当日某条原文） |
| `send_cnt` | INTEGER | 当日该梗发送总条数 |
| `unique_sender_cnt` | INTEGER | 当日不同 uid 数（≥ 阈值才存在） |
| `first_seen` | DATETIME | 当日首次出现 |
| `last_seen` | DATETIME | 当日最后出现 |
| `is_filtered` | BOOLEAN | 降噪标记（默认 0；达标热梗一般为 0） |

索引：`(live_date, send_cnt DESC)` 支撑今日榜；`(content_norm)` 支撑本周聚合。

### `live_hot`（退役）

退役。读取该表的页面改读 `daily_hot`（见下）。表本身可保留为历史只读或在迁移
中删除（实现计划阶段决定）。

## 数据流

### 写入（aggregator，逐条）

照旧：每条 chat 事件归一化后写 `raw_danmaku`，并计算 `is_filtered`。
**不再** per-event upsert `live_hot`（去掉该逻辑）。

### 实时维护（recount_cron，每分钟，频率不敏感）

基于「当前数据日 04:00 至今」的 `raw_danmaku`，按 `content_norm` 聚合：

```
SELECT content_norm,
       COUNT(*)              AS send_cnt,
       COUNT(DISTINCT uid)   AS unique_sender_cnt,
       MIN(ts) AS first_seen, MAX(ts) AS last_seen
FROM raw_danmaku
WHERE ts >= 当前数据日起点(今天 04:00)
  AND content_norm NOT IN (降噪命中)        -- 噪声不计
GROUP BY content_norm
HAVING COUNT(DISTINCT uid) >= 阈值
```

把结果 upsert 进 `daily_hot`（`live_date = 当前数据日`）。一天内 unique 只增不减，
一旦达标即稳定留下。`daily_hot` 因此只含达标热梗，规模为「每日达标梗数 × 在表天数」。

### 04:00 结算（archive_cron，仅清理）

不做任何「决定谁入表」的判定，只两步：

1. 删 `raw_danmaku` 中早于保留窗口（2 天）的行。
2. 删 `daily_hot` 中 `live_date` 早于 `daily_hot_retention_days`（7）天前的行。

不达标内容从未进表，无需额外清理。

## 榜单读取

- **今日 Top 10**：
  `SELECT ... FROM daily_hot WHERE live_date = 今天 ORDER BY send_cnt DESC LIMIT 10`，
  准实时（≤ recount 间隔的延迟）。
- **本周 Top 50**（累计发送量口径）：
  `daily_hot` 最近 7 个 `live_date`，`GROUP BY content_norm` 求 `SUM(send_cnt)`，
  排序取 50。跨天不做 unique 去重。

## 配置（全部走 setting 表，禁止硬编码）

| key | 默认 | 说明 |
|-----|------|------|
| `live_hot_min_unique_senders_24h` | 20 | 入表阈值（已存在） |
| `daily_hot_retention_days` | 7 | `daily_hot` 保留天数（新增） |
| `raw_retention_days` | 2 | raw 缓冲天数（默认值由 30 改 2） |
| `live_noise_filters` / `live_hot_min_length` / `live_hot_max_length` | 照旧 | 计数前生效 |

## 迁移与影响范围

需从 `live_hot` 改读 `daily_hot` 或调整的位置：

- 公开页 `/live`（`templates/live.html`，`data-source="live_hot"`）→ 改为今日榜数据源。
- 后台「直播热门」列表/详情（`routes_admin.py` `/admin/live_hot*`）→ 改读 `daily_hot`。
- 统计页 `stats.html` 的 `live_hot_total` 计数。
- `recount_cron`：重写为上面的 `daily_hot` 维护逻辑。
- `aggregator`：去掉 per-event `live_hot` upsert。
- `archive_cron`：加 `daily_hot` 过期清理。
- `live_hot_recompute` / `live_hot_rescan` 后台工具：因 raw 仅留 2 天，全量重建只能覆盖
  近 2 天；重定向到 `daily_hot` 或在迁移中调整语义/移除（实现阶段决定）。
- Alembic 迁移：新建 `daily_hot` 表 + 索引；`raw_retention_days` 默认值变更；
  `live_hot` 退役处理。

## 容量预估

| | 现状 / 30 天稳态 | 新方案稳态 |
|--|--|--|
| `raw_danmaku` | ~1~1.5 GB | 2 天 × ~14.5 万 ≈ 29 万行 ≈ ~90 MB（含索引） |
| `live_hot` / `daily_hot` | 9.7 万行且无限涨 | 达标梗 × 7 天 ≈ 几百~几千行，< 1 MB |
| **合计** | **GB 级且持续涨** | **稳态封顶 ~90–100 MB，不再增长** |

按用户判断，~14.5 万条/天为单日峰值，后续不会更高，故上限稳定。配合偶尔 `VACUUM`
回收 `DELETE` 后的空闲页可让文件实际收缩。

## 验证

- 单测：`live_date` 边界（03:59 / 04:00 归属）、阈值判定、本周聚合排序。
- 迁移后在 VPS 观察一个数据日周期：04:00 后 raw 行数回落、`daily_hot` 仅留达标梗、
  今日/本周榜数据正确，库文件大小趋于稳定。
