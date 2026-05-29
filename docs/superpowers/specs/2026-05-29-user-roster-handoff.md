# 用户名册（"选自己"功能）——交接文档

> 2026-05-29 整理，供换机/新会话继续。配合 commit `e407b30` 阅读。

## 1. 需求 / 想法

2099 直播间需要一个功能：**列出房间里的活跃用户，让用户从列表里点选"我是谁"**。

- 没有任何接口能拿到"全体在线观众名单"（斗鱼和所有直播平台都不提供，在线人数只是个数字）。
- 能拿到的是**有过可见行为的人**：发过弹幕 / 进过房 / 送过礼 / 上过榜。
- 现成的最全数据源：本人在上海 VPS 跑的 **hyacinth_sentry**（斗鱼礼物/弹幕采集器，8080），其 `events.db` 长期累积。
- 方案定调：**sb2099 只读直连 hyacinth 的 events.db 做一次性"种子"导入**，之后 sb2099 自己维护一份 `user` 表（独立持久，不依赖 hyacinth）。两个项目 git 分开，不改 hyacinth 代码。

## 2. 关键调研结论（避免重走弯路）

- **nb.douyuex.com 这类站点**用的不是斗鱼开放平台 API，而是**网页端/客户端的非公开接口 + 弹幕长连接**。用户信息（uid/昵称/头像/等级）顺着弹幕、礼物广播、榜单接口"漏"出来，匿名即可收公开消息。
- **昵称永远是"发出那一刻的当前昵称"**：斗鱼消息里的 `nn` 不缓存旧名。所以"某 uid 的最新昵称"="该 uid 最近一条事件里的 nn"。改名只要再出现过就自动更新。
- **`https://msg.douyu.com/v3/login/getusersig` 不是头像接口**：实测无登录态返回 `403 Unauthenticated request`。它是 get user **sig**（用户签名），需登录、且只返回**登录者本人**的信息，不能按 uid 批量查任意人头像。**别用它配名册头像。**
- **头像走 raw 里的 `ic` 字段**（见 §4），1459 人里 98% 能直接拿到，无需登录、无频率限制——对批量配头像严格优于任何接口。

## 3. 数据源事实（hyacinth_sentry）

- VPS：SSH 别名 **`aliyun-139`**（139.196.96.110，hostname `iZrcpk842160xgZ`，user root，key `C:/Users/asus/.ssh/codex_ed25519`）。
- 路径：`/opt/hyacinth_sentry`，服务 8080，库 **`/opt/hyacinth_sentry/events.db`**。
- sb2099 也在这台机：`/opt/sb2099`，服务 8090。房间号 `DOUYU_ROOM_ID=12740109`（即 2099）。
- **events 表**（append-only）：`id, ts(epoch ms), room_id, kind, uid, nickname, gift_id, gift_name, count, price_yuchi, content, color, raw, ...`。
  - **入库的 kind 只有 `gift` / `superchat` / `subscription`**；`chat`（普通弹幕）/`uenter`（进房）**不入库**（server.py 里是 broadcast-only）。
  - 所以名册=**付过费 / 送过荧光棒 / 开过钻粉贵族 / 发过高能弹幕的人**，**不含纯发弹幕、纯潜水的观众**。
- **数据不会自动清**：代码里无 TTL/保留期；唯一 DELETE 在 `tools/maintenance/`（`clear_db.py` 等手动脚本）。VPS 上那条 `28 17 * * *` cron 是宝塔 SSL 续期，与 DB 无关。→ 只读直连安全，可随时全量重新对账。
- 实测（2026-05-29）：27990 行 → **1459 个去重 uid**，其中 92 个在采集期改过名。

## 4. 头像：ic 字段

dgb（礼物）raw 里带 `ic@=avatar_v3@S202605@Sxxxxx`。
- 斗鱼一级转义：`@S`→`/`、`@A`→`@`。解码后是路径 `avatar_v3/202605/xxxxx`（默认头像形如 `avatar/default/21`，同样适用）。
- 完整 URL 模板：`https://apic.douyucdn.cn/upload/{ic路径}_{size}.jpg`，`size ∈ {small, middle, big}`（实测三种都 200）。
- **存法决策**：库里只存 ic 路径，渲染时用 `sb2099.users.avatar_url(path, size)` 现拼尺寸（省空间、换尺寸不改库）。

## 5. 本次已完成（commit `e407b30`，已 push 到 origin/main）

| 文件 | 内容 |
|---|---|
| `sb2099/users.py` | 纯逻辑：`decode_ic` / `extract_ic` / `avatar_url` / `build_roster`。`build_roster(rows)` 输入 `(uid, nickname, raw, ts_ms)`，输出 `uid -> {nickname, avatar, first_seen_ms, last_seen_ms}`，取"最新非空"值，缺 ic 不覆盖已有头像。 |
| `sb2099/models.py` | 新增 `User` 模型：`uid`(PK) / `nickname` / `avatar`(ic 路径) / `first_seen` / `last_seen` / `source`(seed\|live)。 |
| `alembic/versions/0007_user.py` | `user` 建表迁移（链到 0006）。 |
| `tools/seed_users_from_hyacinth.py` | 一次性导入器：只读打开源库、dry-run 默认、`--apply` 落库、可重复运行（ON CONFLICT 更新 nickname/avatar/last_seen）。 |
| `tests/test_users.py` | 7 项单测，全过。 |

**已验证**：单测全过；本地 `alembic upgrade head` 跑到 0007、表结构/索引正确；`build_roster` 在真实 events.db 上跑出 1459 uid（昵称 100%、头像 98%）。

**取昵称的名册 SQL（参考）**：
```sql
SELECT uid, nickname AS latest_name, MAX(ts) AS last_seen, COUNT(*) AS events
FROM events WHERE uid IS NOT NULL GROUP BY uid ORDER BY last_seen DESC;
-- 注：裸列+MAX 取同行是 SQLite 专有保证；换库要用窗口函数/DISTINCT ON
```

## 6. 待办（TODO）

1. **上线（改生产，需本人执行/授权）**：
   - 同步本仓库到 `/opt/sb2099`（`git pull`）。
   - `cd /opt/sb2099 && .venv/bin/python -m alembic upgrade head`（生产库建 user 表）。
   - dry-run 预览：`.venv/bin/python -m tools.seed_users_from_hyacinth`（默认源 `/opt/hyacinth_sentry/events.db`）。
   - 落库：`.venv/bin/python -m tools.seed_users_from_hyacinth --apply`（导入约 1459 人）。
2. **往后自维护（待决策）**：是否改 `sb2099/ingest/aggregator.py`，让 sb2099 自己的弹幕也 upsert `User`（`source="live"`），并从 `chatmsg` 的 `ic` 抓头像——这样**纯发弹幕的新人**也能进名册/有头像，完全自给自足、不再依赖 hyacinth。
   - 注意：sb2099 自己的 `raw_danmaku` 有 `raw_retention_days=2`（2 天清），但 `user` 表独立持久不受影响。
3. **前端**：用 `user` 表做"选自己"界面（昵称搜索 + 头像确认，UID 主键）。

## 7. 常用命令

```bash
# 连 VPS / 看服务
ssh aliyun-139
ss -ltnp | grep -E ':8080|:8090'

# 本地跑单测（conda estia 或任何有 sqlalchemy+pytest 的环境）
cd sb2099 && python -m pytest tests/test_users.py -q

# 验证迁移（临时库，跑完即删）
SB2099_ADMIN_TOKEN=xxxxxxxxxxxx SB2099_IP_SALT=xxxxxxxxxxxx SB2099_DB_PATH=./_t.db python -m alembic upgrade head
```
