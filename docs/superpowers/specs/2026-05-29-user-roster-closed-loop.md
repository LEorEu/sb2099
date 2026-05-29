# 设计：用户名册闭环 + 投稿者展示 + 防伪三件套

- 日期：2026-05-29
- 状态：待评审
- 范围：sb2099 ingest 改造（直连 danmuproxy）、user 表实时维护、barrage schema 扩展、投稿表单、公开 API、admin pending 详情、60s 撤回
- 关联：`2026-05-29-user-roster-handoff.md`（前置：建表 + seed 完成）、`2026-05-22-sb2099-requirements-alignment-design.md`（部分反转，见末节）

## 背景与动机

handoff 已经把 user 表建好并从 hyacinth `events.db` 种子了 1462 个 uid（昵称 100%，头像 98.4%）。但有两个关键问题没解决：

1. **不闭环**：种子是一次性的，新观众进 2099 后不会进入名册；hyacinth `/ws/live` 的 broadcast 把 chatmsg 的 `ic / level / bnn / brid / bl / dms` 全部 strip 掉，sb2099 通过现有 WS 链路拿不到这些字段。
2. **强耦合**：sb2099 当前 `ingest/client.py` 订阅 hyacinth `ws://127.0.0.1:8080/ws/live`，hyacinth 不在则 sb2099 也不能采集。违背"从 0 部署也能慢慢得到直播间用户信息"的目标。

实测（2026-05-29，直连 `danmuproxy.douyu.com:8601` 抓 25s）：chatmsg 协议层 **83/83 = 100% 携带 `ic`** + level/bnn/brid/bl/dms。也就是说协议上游就有完整字段，只是被 hyacinth broadcast 那层抹掉了。

## 目标

1. **闭环**：sb2099 自连 danmuproxy，从协议层直接拿 chat + 用户字段；新观众一发言就进 user 表，头像随后自动更新。
2. **自给**：sb2099 不再依赖 hyacinth 的任何运行时数据流（hyacinth 仍可作为离线种子源，但不是 runtime 依赖）。
3. **可选展示**：投稿条目可以选择关联自己的 uid，列表 hover 显示昵称+头像；也允许匿名（不选 uid 或选了又勾"本条匿名"）。
4. **轻度防伪**：三个后台探测器把可疑投稿自动进 pending；admin 详情提供该 uid 最近活跃证据；用户有 60s 反悔窗口。

非目标：
- 不做用户系统/登录/信任分/等级门槛/直播间弹幕质询（已讨论排除）。
- 不阻断匿名投稿；防伪只是把可疑稿降级到 pending，不拒绝。

## 系统架构

```
       斗鱼 danmuproxy:8601 (TCP, 斗鱼自有协议)
                 │
                 │  chatmsg frame
                 ▼
   sb2099/ingest/danmu_tcp.py  ◄─── 新增，复用 hyacinth 的协议格式
                 │              （不 import hyacinth 代码，按协议自实现）
                 │  dict(uid, nn, txt, ic, level, bnn, brid, bl, dms, col, ts)
                 ▼
   sb2099/ingest/aggregator.py
       ├─► RawDanmaku (现状不变)
       └─► User upsert (新增, source="live")
```

旧 `ingest/client.py`（hyacinth /ws/live）**删除**。`DOUYU_LIVE_WS_URL` 配置项一并从 `config.py` 移除。回滚靠 git revert 这次 commit，不留死代码。

## 数据模型

### `user` 表（已存在，0007 已上线）

字段不动。`source` 字段：
- `seed`：从 hyacinth events.db 一次性导入（已完成，1462 行）。
- `live`：通过 sb2099 自己的 danmu_tcp 实时 upsert。

### `barrage` 表（0008 扩展）

新增列：

```sql
ALTER TABLE barrage ADD COLUMN submitter_uid TEXT NULL;
CREATE INDEX ix_barrage_submitter ON barrage(submitter_uid)
       WHERE submitter_uid IS NOT NULL;
```

- 不加外键约束（SQLite 加 FK 需 rebuild 表）。应用层校验 uid 是否在 user 表里。
- 校验失败（uid 不存在/被踢出名册）→ 当作匿名投稿（submitter_uid = NULL），不报错。
- 已展开的公开列表 LEFT JOIN user，不需要二次查询。

### `setting` 表新增键

| key | 类型 | 默认 | 含义 |
|---|---|---|---|
| `submission_anti_fraud_enabled` | bool | true | 总开关，关掉则跳过所有探测器 |
| `submission_uid_multi_ip_window_days` | int | 7 | "同 uid 多 IP hash" 探测窗口 |
| `submission_uid_multi_ip_threshold` | int | 5 | 不同 IP hash 数阈值（含本次） |
| `submission_uid_inactive_days` | int | 30 | "uid 活跃度脱节" 阈值（≥N 天未发言即脱节） |
| `submission_uid_unseen_blocks` | bool | true | "uid 与房间无交集"（raw_danmaku 从未出现）是否进 pending |
| `submission_withdraw_window_seconds` | int | 60 | 撤回窗口 |

均通过现有 admin settings 页面 UI 可改，运行时生效（settings_cache 已经支持热更新）。

## ingest 改造

### `sb2099/ingest/danmu_tcp.py`（新增, ≤200 行硬上限）

仿 hyacinth `protocol.py` 的实现，按斗鱼私有协议自实现 4 个函数：
- `encode(body: str) -> bytes`：12 字节头 + body
- `iter_frames(buf: bytearray) -> Iterator[(int, str)]`：消费缓冲返出完整 frame
- `parse_kv(body: str) -> dict[str, str]`：`/` 分隔字段、`@=` 分隔键值
- `login_req(rid) / join_group(rid) / heartbeat()`：登录/加群/心跳

主循环 `stream_chat_events()`（替代 client.py 的同名函数）：
- 连接 `danmuproxy.douyu.com:8601`
- loginreq → joingroup(rid=ROOM, gid=-9999) → 45s 心跳
- 解 frame，过滤 `type=="chatmsg"`，yield 标准化 dict：

```python
{
    "ts": <epoch_ms>,
    "kind": "chat",
    "uid": kv["uid"],
    "nickname": kv["nn"],
    "content": kv["txt"],
    "color": int(kv.get("col") or 0) or None,
    "ic": kv.get("ic"),         # 已经解过 @S→/ @A→@ 转义（实测 parse_kv 返回的就是解码值）
    "level": int(kv.get("level") or 0) or None,
    "bnn": kv.get("bnn"),        # 粉丝牌昵称
    "brid": kv.get("brid"),
    "bl": int(kv.get("bl") or 0) or None,
    "dms": kv.get("dms"),
}
```

- 断线 5s 重连（与 client.py 一致策略）。
- 完全不引 hyacinth 代码（按 spec 边界）。

### `sb2099/ingest/aggregator.py`（扩展）

加一个 `persist_user_from_chat(evt)`：

```python
def persist_user_from_chat(evt):
    uid = evt.get("uid")
    if not uid:
        return
    ic = evt.get("ic")  # 协议已解码
    now = datetime.utcnow()  # naive UTC，与现有时间存法一致
    with _db.SessionLocal() as session:
        session.execute(
            sqlite_insert(User).values(
                uid=uid,
                nickname=evt.get("nickname"),
                avatar=ic,
                first_seen=now,
                last_seen=now,
                source="live",
            ).on_conflict_do_update(
                index_elements=["uid"],
                set_={
                    "nickname": evt.get("nickname") or User.nickname,
                    # 头像有变才更新，空值不覆盖（防止某条 chatmsg ic 偶发缺失）
                    "avatar": case((sa.literal(ic).is_not(None), ic), else_=User.avatar),
                    "last_seen": now,
                },
            )
        )
        session.commit()
```

注意点：
- 不写 `source="seed"` 的旧记录的 source 字段；新人首次 upsert 走 `source="live"`，已是 seed 的不动 source。
- 昵称/头像更新策略：非空才覆盖（避免偶发的字段缺失把已有数据冲掉）。
- 此函数与 `persist_chat_event` 并行调用；两路都走 `asyncio.to_thread`，DB 短事务。

### `sb2099/ingest/worker.py`（小改）

唯一数据源改为 `danmu_tcp.stream_chat_events()`。对外 API 不变。

```python
from .danmu_tcp import stream_chat_events

async def run():
    async for evt in stream_chat_events():
        try:
            await persist_chat_event(evt)
            await persist_user_from_chat(evt)
        except Exception:
            log.exception(...)
```

## 防伪探测器

新模块 `sb2099/web/submission_review.py`：

```python
def review_submission(content_norm, submitter_uid, ip_hash, session) -> tuple[str, str | None]:
    """返回 (status, reason)。status ∈ {'active','pending'}。"""
    if not get_settings_cache("submission_anti_fraud_enabled", True):
        return "active", None
    # ... 内容投稿待审规则（已存在）也走这里
    if not submitter_uid:
        return "active", None  # 匿名稿不触发名册探测器
    # 探测器 1: 该 uid 在 raw_danmaku 从未出现
    if get_settings_cache("submission_uid_unseen_blocks", True):
        if not session.query(RawDanmaku).filter_by(uid=submitter_uid).first():
            return "pending", "uid_never_seen_in_room"
    # 探测器 2: 该 uid 最近 N 天没说话
    inactive_days = get_settings_cache("submission_uid_inactive_days", 30)
    cutoff = utcnow() - timedelta(days=inactive_days)
    last = session.query(func.max(RawDanmaku.ts)).filter_by(uid=submitter_uid).scalar()
    if last and last < cutoff:
        return "pending", f"uid_inactive_{inactive_days}d"
    # 探测器 3: 同 uid 跨多 IP（短期）
    window_days = get_settings_cache("submission_uid_multi_ip_window_days", 7)
    threshold = get_settings_cache("submission_uid_multi_ip_threshold", 5)
    window_cutoff = utcnow() - timedelta(days=window_days)
    rows = session.query(Barrage.submitter_ip_hash).filter(
        Barrage.submitter_uid == submitter_uid,
        Barrage.submit_time >= window_cutoff,
    ).distinct().all()
    distinct_hashes = {h for h, in rows if h}
    distinct_hashes.add(ip_hash)
    if len(distinct_hashes) >= threshold:
        return "pending", f"uid_distinct_ip_hashes_{len(distinct_hashes)}"
    return "active", None
```

说明：barrage 表存的是 `sha256(ip + salt)[:16]` 哈希，无法反推 /24 子网。直接对 hash 去重计数：
- 同一 NAT 后所有用户共享公网 IP → 同 hash → 不会互相触发
- 同一用户家 wifi/手机/办公室间切换 → 不同 hash → 一周内累积 3-4 个属正常
- 阈值 5：典型恶意刷稿场景（代理 / IP 池）才会突破 5

调用点：`web/routes_public.py` 的投稿处理函数，在 INSERT 前调用，根据返回的 (status, reason) 决定 barrage.status 字段和写入 audit log（新增一列 `review_reason TEXT` 复用现有 pending 机制；如果现有 pending 没有 reason 列，alembic 0008 一起加）。

## 投稿表单 UX

### 投稿组件（前端 sb2099.js + templates 共用 partial）

- 默认状态：底部一个小条 "选择我是谁（可选）"
- 点开：弹一个轻量下拉，按昵称模糊搜索 user 表（API: `GET /api/users/search?q=xxx&limit=10`）
- 选中后显示 [头像 昵称] chip + "❌ 改成匿名"
- 即使选了 uid，表单底部仍保留一个独立勾选 "本条匿名投稿"（默认不勾）。勾了 → 提交时 submitter_uid = NULL；不勾 → 提交 submitter_uid

理由：你"选择了 uid 也能匿名"的需求 = 不让用户在"换号"与"匿名"之间反复选 chip，而是允许"全程绑定身份" + "本条临时不署名"两种状态独立。

### `GET /api/users/search`

```python
@router.get("/api/users/search")
@limiter.limit(...)  # 复用 copy 端点限频（slowapi）
def search_users(request: Request, q: str = "", limit: int = 10):
    q = q.strip()
    if len(q) <= 2:  # 必须 > 2 字符，避免单字昵称把全名册拉出来
        return {"results": []}
    limit = min(max(limit, 1), 10)
    if q.isdigit():
        # 全数字 → 按 uid 精确 or 前缀匹配（兼容"2 字昵称用户用 uid 自助查找"）
        rows = session.query(User).filter(User.uid.like(f"{q}%")).order_by(
            User.last_seen.desc()
        ).limit(limit).all()
    else:
        rows = session.query(User).filter(User.nickname.like(f"%{q}%")).order_by(
            User.last_seen.desc()
        ).limit(limit).all()
    return {"results": [
        {"uid": u.uid, "nickname": u.nickname, "avatar": avatar_url(u.avatar)}
        for u in rows
    ]}
```

设计要点：
- **q 必须 > 2 字符**（≥3），防止 `?q=` 直接拉全名册
- **全数字 = uid 模式**：兼容 2 字昵称用户（让他们用 uid 自助搜）
- 返回上限 10 条，按 last_seen DESC（活跃用户优先）
- 返回 avatar 已是完整 URL，前端不拼

## 公开列表 API

### 修改 `GET /api/barrage` 和 `home` 页面预览

LEFT JOIN user，每条加：

```python
{
    "id": ..., "content": ..., "tags": [...],
    "submitter": null | {"nickname": "xxx", "avatar": "https://..."}
}
```

**不返回 uid**。避免被批量爬"哪些 uid 在 sb2099 投稿"（隐私最小化）。

### 前端 tooltip

barrage 卡片渲染：如果 `submitter` 非空，加 `title` 属性或自定义 tooltip（hover 显示 `<img> 由 xxx 投稿`）。匿名稿无 tooltip。

## admin pending 详情侧栏

`templates/admin/pending.html` 详情页（点开某条 pending 时），右侧加一个块：

```
[头像] 投稿人: 桜洛洛洛洛 (uid=328686222)
等级: 19  粉丝牌: 一团肉松子 / 17  最后说话: 5 分钟前

—— 最近 5 条弹幕（来自 raw_danmaku）——
2026-05-29 19:55  哈哈哈不让发了
2026-05-29 19:53  这波操作
2026-05-29 19:51  yysy 真的
2026-05-29 19:48  xxx
2026-05-29 19:42  yyy
```

数据源：
- 投稿人信息 = user 表行
- 最近弹幕 = `SELECT ts, content_raw FROM raw_danmaku WHERE uid=? ORDER BY ts DESC LIMIT 5`

匿名稿（submitter_uid NULL）只显示 IP hash 摘要（与现状一致）。

如果有 `review_reason` 字段，详情顶部显示一行红字 "命中规则：uid_inactive_30d"。

## 60s 撤回窗口

### 服务端

```python
@router.delete("/api/submission/{barrage_id}/withdraw")
def withdraw(barrage_id: int, request: Request):
    token = request.cookies.get(f"sb_recent_{barrage_id}")
    if not token:
        raise HTTPException(404)
    record = _verify_recent_token(token, barrage_id)  # HMAC; payload = ip_hash + expires_at
    if record.expires_at < utcnow():
        raise HTTPException(410, "withdraw window expired")
    # 校验当前请求 IP hash 与 cookie 里 record.ip_hash 一致（防 cookie 泄漏被他人撤）
    if hash_ip(request) != record.ip_hash:
        raise HTTPException(403)
    # 直接物理删除：HMAC + IP + 60s 三重校验已足够，不再 join admin 状态
    session.query(Barrage).filter_by(id=barrage_id).delete()
    return {"ok": True}
```

撤回**只校验 60s 窗口 + HMAC + IP 一致**，不管 barrage 当前 status/admin 是否介入过：
- 若 admin 已通过 pending 稿 → 用户撤回也只是删了一条合规稿，admin 不损失什么
- 若 admin 已软删 → status 变 'deleted'，DELETE 还是会真删，幂等
- 避免无谓摩擦：60s 内 admin 动手概率本来就极低

提交成功响应时 set-cookie：

```
Set-Cookie: sb_recent_<id>=<hmac_token>; Max-Age=60; HttpOnly; SameSite=Strict; Path=/
```

token 用 SB2099_IP_SALT 作 HMAC 密钥（已有，不引新 secret）。

### 前端

提交成功后弹一个 toast："已发布 · 60秒内可撤回 [撤回]"，倒计时按钮，到点禁用。

撤回会**物理删除** barrage（含 FTS 索引，由现有 `barrage_ad` trigger 处理）。

## 配置与部署

### config.py 改动

`DOUYU_LIVE_WS_URL` 默认值改空字符串。danmuproxy 直连用硬编码 host（`danmuproxy.douyu.com:8601`）或新增 `DOUYU_DANMUPROXY_HOST`（默认上述值）。倾向硬编码（斗鱼这个 endpoint 几年没变）。

### alembic 0008 总览

一个 migration 完成：
1. `barrage.submitter_uid TEXT NULL` + 索引
2. `barrage.review_reason TEXT NULL`（新增，pending 命中规则名落地用）
3. 6 个 setting 默认值（OR IGNORE 插入）

### 部署顺序（一次重启）

1. 本地写完代码、跑 pytest 通过、commit、push
2. git bundle → scp → VPS git merge --ff-only
3. VPS alembic upgrade head（仅跑 0008，建表/加列不动数据）
4. **告知用户、等用户同意** → `systemctl restart sb2099`（5-10s 窗口）
5. journalctl 验证 danmu_tcp 连上、user 表 last_seen 字段开始有 source='live' 的更新

回滚预案：
- 若 danmu_tcp 不稳定 → `git revert <Phase-B commit>` → bundle → 部署 → 重启回到 hyacinth 通道
- 若 alembic 0008 出问题 → 备份在 `/opt/sb2099-backup-XXXX.db`（每次部署前先 sqlite .backup）；`alembic downgrade -1` 也可
- danmu_tcp 与 hyacinth 不能并存运行，避免 user 表 upsert 竞态

## 测试

- `tests/test_danmu_tcp.py`：用录制的字节流测试 protocol 解析、frame 切分、kv 解析、login_req 字节长度
- `tests/test_user_updater.py`：fake session 验证 upsert 行为（新人 source=live、已 seed 不动 source、空值不覆盖、头像变化更新）
- `tests/test_submission_review.py`：每个探测器独立单测（用内存 DB 装 fixture）
- `tests/test_withdraw.py`：cookie + HMAC + IP 一致性 + 过期
- `tests/test_api_users_search.py`：搜索、限频、avatar URL 拼接

## 与 2026-05-22 spec 的反转

`docs/superpowers/specs/2026-05-22-sb2099-requirements-alignment-design.md` §"普通投稿" 写："**公开投稿不展示投稿者信息**"。

本 spec **部分反转**该条：
- 允许（但不强制）展示投稿者**昵称+头像**，**不展示 uid**
- 用户可在投稿表单选择"本条匿名"使该条不展示
- 完全不选 uid 的稿继续匿名展示，与 2026-05-22 一致

反转的原因：原 spec 的"不展示投稿者信息"基于"投稿需要登录"的隐忧；现在改为"无注册自愿选 uid"后，展示昵称成为**对认领者的微正反馈**，鼓励真人投稿；不展示 uid 保持了 2026-05-22 spec "不识别个体"的隐私底线。

## 不做（已讨论排除）

- per-uid 限频（"想刷就刷嘛"，IP 限频已够）
- 新网络环境提醒（探测器已覆盖）
- 用户信任分（开了用户系统的口子，违背 spec）
- 等级/粉丝牌门槛（挡新人）
- 直播间弹幕质询（影响直播体验、操作多一步）
