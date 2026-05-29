# daily_hot 保留策略重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `raw_danmaku` 降级为 2 天缓冲，用按日热梗表 `daily_hot`（单日 ≥ 阈值 unique sender 才入表）替换 `live_hot`，封住数据库增长上限。

**Architecture:** 抓取层只写 `raw_danmaku`（一条一行）。`recount_cron` 每分钟从当前数据日（CST 04:00→次日 04:00）的 raw 聚合，把达标内容 upsert 进 `daily_hot`。`archive_cron` 每日清过期 raw（2 天）和过期 `daily_hot`（7 天）。读取层：今日 Top10 取 `daily_hot` 当日行，本周 Top50 聚合最近 7 个数据日。API/前端契约（`source="live_hot"`、`live_hot_id`）保持不变，仅把底层表指向 `daily_hot`。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2.x（Core text SQL + ORM）、SQLite(WAL)、Alembic、pytest。

> 工作目录：`D:\TTS\sb2099`。所有路径相对该目录。所有命令在该目录下、激活 `.venv` 后运行（`.\.venv\Scripts\Activate.ps1`）。

---

## 设计基线（贯穿全计划，类型/命名必须一致）

**数据日（live_date）**：CST(UTC+8) 04:00 → 次日 04:00。标签是 `date`，存库用 ISO 字符串 `'YYYY-MM-DD'`（字符串字典序 == 日期序）。

**新模块 `sb2099/live_day.py`** 导出：
- `current_live_window(now_utc_naive: datetime) -> tuple[date, datetime]` → (当前数据日, 该数据日起点的 UTC naive 时刻)
- `live_date_of(ts_utc_naive: datetime) -> date`

**`DailyHot` 模型字段**（替换 `LiveHot`）：`id` PK、`live_date` String(10)、`content_norm` Text、`content_sample` Text、`send_cnt` Integer、`unique_sender_cnt` Integer、`first_seen`/`last_seen` DateTime、`page_copy_cnt` Integer、`is_filtered` Boolean；`UniqueConstraint("live_date","content_norm", name="uq_daily_live_norm")`。

**setting 键**：阈值 `live_hot_min_unique_senders_24h`（默认 20）、`raw_retention_days`（默认 2）、`daily_hot_retention_days`（默认 7）。

**API 契约不变**：`/api/copy` 的 `source` 仍可为 `"live_hot"`、`/api/promote` 仍用字段 `live_hot_id`，但都按 `DailyHot.id` 解析。前端模板/JS 不改。

时间：所有 `ts` 为 UTC naive（`datetime.fromtimestamp(ms/1000, tz=utc).replace(tzinfo=None)`）。

---

## 文件结构（创建/修改）

- Create: `sb2099/live_day.py` — 数据日纯函数
- Create: `alembic/versions/0005_daily_hot.py` — 建 daily_hot、删 live_hot、改 setting 默认值
- Create: `tests/test_live_day.py`
- Modify: `sb2099/models.py` — 删 `LiveHot`、加 `DailyHot`
- Modify: `sb2099/config.py` — DEFAULTS 改值
- Modify: `sb2099/ingest/aggregator.py` — 去掉 live_hot upsert，只写 raw；保留 `should_filter`
- Modify: `sb2099/cron.py` — 重写 `_recount_sync`（建 daily_hot）、`_archive_sync`（清 raw+daily_hot）
- Modify: `sb2099/web/routes_api.py` — `/api/live`、`/api/copy`、`/api/promote` 指向 daily_hot
- Modify: `sb2099/web/routes_public.py` — `/live` 页指向 daily_hot
- Modify: `sb2099/web/routes_admin.py` — live_hot 列表/详情/recompute/rescan/stats 指向 daily_hot
- Modify: `sb2099/web/templates/admin/live_hot_detail.html` — `send_cnt_total` → `send_cnt`
- Modify: `tests/test_aggregator.py`、`tests/test_cron.py`、`tests/test_routes_api.py`、`tests/test_routes_public.py`、`tests/test_routes_admin.py`

---

## Task 1: 数据日纯函数 `live_day.py`

**Files:**
- Create: `sb2099/live_day.py`
- Test: `tests/test_live_day.py`

- [ ] **Step 1: 写失败测试**

`tests/test_live_day.py`：

```python
"""数据日边界（CST 04:00）纯函数测试。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sb2099.live_day import current_live_window, live_date_of

CST = timezone(timedelta(hours=8))


def _utc_naive(y, mo, d, h, mi, tz=CST):
    """构造某时区本地时刻对应的 UTC naive。"""
    return datetime(y, mo, d, h, mi, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)


def test_live_date_of_before_4am_is_previous_day():
    # CST 2026-05-29 03:59 → 属于数据日 2026-05-28
    ts = _utc_naive(2026, 5, 29, 3, 59)
    assert live_date_of(ts) == date(2026, 5, 28)


def test_live_date_of_at_4am_is_same_day():
    ts = _utc_naive(2026, 5, 29, 4, 0)
    assert live_date_of(ts) == date(2026, 5, 29)


def test_current_live_window_after_4am():
    now = _utc_naive(2026, 5, 29, 10, 0)
    live_date, start_utc = current_live_window(now)
    assert live_date == date(2026, 5, 29)
    # 起点 = CST 2026-05-29 04:00 == UTC 2026-05-28 20:00
    assert start_utc == datetime(2026, 5, 28, 20, 0)


def test_current_live_window_before_4am_rolls_back():
    now = _utc_naive(2026, 5, 29, 2, 0)
    live_date, start_utc = current_live_window(now)
    assert live_date == date(2026, 5, 28)
    assert start_utc == datetime(2026, 5, 27, 20, 0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_live_day.py -v`
Expected: FAIL（`ModuleNotFoundError: sb2099.live_day`）

- [ ] **Step 3: 实现 `sb2099/live_day.py`**

```python
"""数据日（live_date）边界纯函数：CST(UTC+8) 04:00 → 次日 04:00。

ingest/cron/web 统一从这里取「当前数据日」与「某弹幕归属数据日」，禁止各处自行
拼时区/小时。所有入参为 UTC naive（与库内 ts 一致）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
_LIVE_DAY_START_HOUR = 4

__all__ = ["current_live_window", "live_date_of", "CST"]


def current_live_window(now_utc_naive: datetime) -> tuple[date, datetime]:
    """返回 (当前数据日, 该数据日起点的 UTC naive 时刻)。"""
    now_cst = now_utc_naive.replace(tzinfo=timezone.utc).astimezone(CST)
    start_cst = now_cst.replace(hour=_LIVE_DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if now_cst < start_cst:
        start_cst -= timedelta(days=1)
    live_date = start_cst.date()
    start_utc = start_cst.astimezone(timezone.utc).replace(tzinfo=None)
    return live_date, start_utc


def live_date_of(ts_utc_naive: datetime) -> date:
    """某条弹幕（UTC naive）归属的数据日。"""
    ts_cst = ts_utc_naive.replace(tzinfo=timezone.utc).astimezone(CST)
    return (ts_cst - timedelta(hours=_LIVE_DAY_START_HOUR)).date()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_live_day.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add sb2099/live_day.py tests/test_live_day.py
git commit -m "feat(sb2099): add live_day boundary helpers (CST 04:00)"
```

---

## Task 2: DailyHot 模型 + Alembic 迁移 + config 默认值

**Files:**
- Modify: `sb2099/models.py:29-49`（`LiveHot` → `DailyHot`）
- Modify: `sb2099/config.py:41-54`（DEFAULTS）
- Create: `alembic/versions/0005_daily_hot.py`

- [ ] **Step 1: 改 `sb2099/models.py`**

删除整个 `class LiveHot(...)`（第 29–49 行），替换为：

```python
class DailyHot(Base):
    __tablename__ = "daily_hot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    live_date: Mapped[str] = mapped_column(String(10), nullable=False)
    content_norm: Mapped[str] = mapped_column(Text, nullable=False)
    content_sample: Mapped[str] = mapped_column(Text, nullable=False)
    send_cnt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_sender_cnt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    page_copy_cnt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_filtered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("live_date", "content_norm", name="uq_daily_live_norm"),
        Index("ix_daily_date_send", "live_date", "send_cnt"),
        Index("ix_daily_norm", "content_norm"),
    )
```

（`String`/`UniqueConstraint`/`Index` 等已在文件头 import，无需新增。）

- [ ] **Step 2: 改 `sb2099/config.py` DEFAULTS**

`sb2099/config.py:42` 把 `"live_hot_min_unique_senders_24h": 3,` 改为 `20`；
`sb2099/config.py:53` 把 `"raw_retention_days": 30,` 改为 `2,`；
在 `raw_retention_days` 后新增一行 `"daily_hot_retention_days": 7,`。改后这三行为：

```python
    "live_hot_min_unique_senders_24h": 20,
    ...
    "raw_retention_days": 2,
    "daily_hot_retention_days": 7,
```

- [ ] **Step 3: 写迁移 `alembic/versions/0005_daily_hot.py`**

```python
"""replace live_hot with daily_hot; tighten retention settings

Revision ID: 0005_daily_hot
Revises: 0004_add_live_hot_max_length
Create Date: 2026-05-29
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_daily_hot"
down_revision: str | None = "0004_add_live_hot_max_length"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_hot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("live_date", sa.String(length=10), nullable=False),
        sa.Column("content_norm", sa.Text(), nullable=False),
        sa.Column("content_sample", sa.Text(), nullable=False),
        sa.Column("send_cnt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_sender_cnt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("page_copy_cnt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_filtered", sa.Boolean(), nullable=False, server_default="0"),
        sa.UniqueConstraint("live_date", "content_norm", name="uq_daily_live_norm"),
    )
    op.create_index("ix_daily_date_send", "daily_hot", ["live_date", "send_cnt"])
    op.create_index("ix_daily_norm", "daily_hot", ["content_norm"])

    op.drop_table("live_hot")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    # 既有库这两个值要按新策略下调（瘦身意图），故 UPSERT 覆盖
    for key, val in (("raw_retention_days", 2), ("live_hot_min_unique_senders_24h", 20)):
        bind.execute(
            sa.text(
                "INSERT INTO setting(key, value, updated_at) VALUES (:k, :v, :u) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
            ),
            {"k": key, "v": json.dumps(val), "u": now},
        )
    bind.execute(
        sa.text("INSERT OR IGNORE INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
        {"k": "daily_hot_retention_days", "v": json.dumps(7), "u": now},
    )


def downgrade() -> None:
    op.create_table(
        "live_hot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content_norm", sa.Text(), nullable=False, unique=True),
        sa.Column("content_sample", sa.Text(), nullable=False),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("page_copy_cnt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("send_cnt_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("send_cnt_7d", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("send_cnt_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_sender_cnt_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_sender_cnt_7d", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_filtered", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.drop_table("daily_hot")
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM setting WHERE key='daily_hot_retention_days'"))
```

- [ ] **Step 4: 跑迁移到临时库确认无报错**

Run（PowerShell，临时库验证 upgrade/downgrade 往返）:
```powershell
$env:SB2099_ADMIN_TOKEN="x"*16; $env:SB2099_IP_SALT="x"*8; $env:SB2099_DB_PATH="$env:TEMP\m5.db"
if (Test-Path $env:SB2099_DB_PATH) { Remove-Item $env:SB2099_DB_PATH }
alembic upgrade head; if ($?) { alembic downgrade -1 }; if ($?) { alembic upgrade head }
```
Expected: 三步均无 traceback，末尾停在 head。

- [ ] **Step 5: 提交**

```bash
git add sb2099/models.py sb2099/config.py alembic/versions/0005_daily_hot.py
git commit -m "feat(sb2099): daily_hot table + migration; tighten retention defaults"
```

---

## Task 3: 简化 aggregator（只写 raw）

**Files:**
- Modify: `sb2099/ingest/aggregator.py`（`_persist_sync` 去掉 live_hot upsert）
- Modify: `tests/test_aggregator.py`（重写为只断言 raw）

- [ ] **Step 1: 重写 `tests/test_aggregator.py`**

整文件替换为（aggregator 不再写 live_hot，噪声判定移交 recount，本文件只测 raw 入库与归一化）：

```python
"""aggregator: 只把 chat 事件写入 raw_danmaku（不再聚合 live_hot）。"""
from __future__ import annotations

from sqlalchemy import select

from sb2099.ingest.aggregator import _persist_sync
from sb2099.models import RawDanmaku


def _evt(content: str, uid: str = "u1", ts_ms: int = 1779530000000) -> dict:
    return {
        "ts": ts_ms,
        "room_id": 12740109,
        "kind": "chat",
        "uid": uid,
        "nickname": "test",
        "content": content,
        "color": None,
    }


def test_chat_inserts_raw(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt("打 rl"))
    with SessionLocal() as s:
        rows = s.execute(select(RawDanmaku)).scalars().all()
        assert len(rows) == 1
        assert rows[0].content_raw == "打 rl"
        assert rows[0].content_norm == "打rl"
        assert rows[0].uid == "u1"


def test_repeat_inserts_multiple_raw(tmp_db):
    from sb2099.db import SessionLocal
    for i in range(5):
        _persist_sync(_evt("加一", uid=f"u{i}", ts_ms=1779530000000 + i * 1000))
    with SessionLocal() as s:
        assert len(s.execute(select(RawDanmaku)).scalars().all()) == 5


def test_normalized_value_stored(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt("打ｒｌ"))
    with SessionLocal() as s:
        row = s.execute(select(RawDanmaku)).scalar_one()
        assert row.content_norm == "打rl"


def test_empty_content_dropped(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt(""))
    _persist_sync(_evt("   "))
    with SessionLocal() as s:
        assert s.execute(select(RawDanmaku)).scalars().all() == []
```

> 注：`"打 rl"` 归一化后期望 `"打rl"`（空格折叠）。若实测不符，按 `normalize()` 实际输出调整该断言——不要改 `normalize`。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_aggregator.py -v`
Expected: FAIL（旧 `_persist_sync` 仍 import LiveHot / 行为不符或 import 报错）

- [ ] **Step 3: 改 `sb2099/ingest/aggregator.py`**

- 删除 `from ..models import LiveHot, RawDanmaku` 中的 `LiveHot`，改为 `from ..models import RawDanmaku`。
- 删除 `from sqlalchemy import select, update`（`_persist_sync` 不再用 select/update）→ 改为不 import 这两个（`sqlite_insert` 仍需要）。
- 把 `_persist_sync` 整个函数体替换为（只写 raw）：

```python
def _persist_sync(evt: dict) -> None:
    ts_ms = evt.get("ts")
    if not isinstance(ts_ms, (int, float)):
        return
    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    content_raw = evt.get("content") or ""
    if not content_raw:
        return
    content_norm = normalize(content_raw)
    if not content_norm:
        return

    with _db.SessionLocal() as session:
        session.execute(
            sqlite_insert(RawDanmaku).values(
                ts=ts,
                uid=evt.get("uid"),
                nickname=evt.get("nickname"),
                content_raw=content_raw,
                content_norm=content_norm,
            )
        )
        session.commit()
```

保留 `should_filter`、`_noise_match`、`_is_decorated_noise`、`_is_low_quality`、`_normalized_filters` 不动（recount 会复用 `should_filter`）。`__all__` 保持 `["persist_chat_event", "should_filter"]`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_aggregator.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add sb2099/ingest/aggregator.py tests/test_aggregator.py
git commit -m "refactor(sb2099): aggregator only writes raw_danmaku"
```

---

## Task 4: 重写 recount（构建 daily_hot）

**Files:**
- Modify: `sb2099/cron.py`（`_recount_sync` + `_RECOUNT_SQL` 替换）
- Modify: `tests/test_cron.py`（recount 部分）

- [ ] **Step 1: 写失败测试（替换 `tests/test_cron.py` 的 recount 用例）**

把 `tests/test_cron.py` 顶部 import 改为：

```python
from sb2099.cron import _archive_sync, _recount_sync
from sb2099.ingest.aggregator import _persist_sync
from sb2099.models import DailyHot, RawDanmaku
from sb2099.settings import settings_cache
```

并把 `test_recount_send_cnt_24h` 替换为下面两个用例（阈值在测试里调小到 2，避免造 20 个 uid）：

```python
def _set_threshold(value: int) -> None:
    import json
    from datetime import datetime as _dt
    from sb2099.db import SessionLocal
    from sb2099.models import Setting
    with SessionLocal() as s:
        s.execute(
            update(Setting)
            .where(Setting.key == "live_hot_min_unique_senders_24h")
            .values(value=json.dumps(value), updated_at=_dt.utcnow())
        )
        s.commit()
    settings_cache.invalidate()


def test_recount_promotes_when_threshold_met(tmp_db):
    from sb2099.db import SessionLocal
    _set_threshold(2)
    now = datetime.utcnow().replace(microsecond=0)
    # 同一内容，3 个不同 uid（达标，阈值 2）
    _persist_sync(_evt("加一", "u1", now - timedelta(minutes=1)))
    _persist_sync(_evt("加一", "u2", now - timedelta(minutes=2)))
    _persist_sync(_evt("加一", "u3", now - timedelta(minutes=3)))

    _recount_sync()
    with SessionLocal() as s:
        row = s.execute(select(DailyHot)).scalar_one()
        assert row.content_norm == "加一"
        assert row.send_cnt == 3
        assert row.unique_sender_cnt == 3


def test_recount_skips_below_threshold(tmp_db):
    from sb2099.db import SessionLocal
    _set_threshold(3)
    now = datetime.utcnow().replace(microsecond=0)
    # 只有 2 个不同 uid < 阈值 3
    _persist_sync(_evt("没火", "u1", now - timedelta(minutes=1)))
    _persist_sync(_evt("没火", "u2", now - timedelta(minutes=2)))

    _recount_sync()
    with SessionLocal() as s:
        assert s.execute(select(DailyHot)).scalars().all() == []


def test_recount_skips_noise(tmp_db):
    from sb2099.db import SessionLocal
    _set_threshold(2)
    now = datetime.utcnow().replace(microsecond=0)
    # "+1" 是默认 live_noise_filters 命中项 → 即便达标也不入 daily_hot
    _persist_sync(_evt("+1", "u1", now - timedelta(minutes=1)))
    _persist_sync(_evt("+1", "u2", now - timedelta(minutes=2)))

    _recount_sync()
    with SessionLocal() as s:
        assert s.execute(select(DailyHot)).scalars().all() == []
```

> `_evt` 已在文件中定义（生成 chat 事件，ts 为 UTC）。`update`/`select` 已 import；若未，补 `from sqlalchemy import select, update`。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_cron.py -v`
Expected: FAIL（旧 `_recount_sync` 更新的是 live_hot；`DailyHot` 无行）

- [ ] **Step 3: 重写 `sb2099/cron.py` recount 部分**

- import 增加：`from .ingest.aggregator import should_filter`、`from .live_day import current_live_window`。
- 删除模块级 `_RECOUNT_SQL`（整段 text 常量）。
- 把 `_recount_sync` 替换为：

```python
def _recount_sync() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, day_start = current_live_window(now)
    live_date_str = live_date.isoformat()
    threshold = int(settings_cache.get("live_hot_min_unique_senders_24h", 20) or 0)

    with _db.SessionLocal() as session:
        rows = session.execute(
            text(
                "SELECT content_norm, content_raw AS sample, "
                "COUNT(*) AS send_cnt, COUNT(DISTINCT uid) AS uniq, "
                "MIN(ts) AS first_seen, MAX(ts) AS last_seen "
                "FROM raw_danmaku WHERE ts >= :start "
                "GROUP BY content_norm HAVING COUNT(DISTINCT uid) >= :thr"
            ),
            {"start": day_start, "thr": threshold},
        ).mappings().all()

        qualifiers = [r for r in rows if not should_filter(r["content_norm"])]
        keep = {r["content_norm"] for r in qualifiers}

        # 阈值被调高 / 内容变噪声 → 删掉当日已不达标的行
        existing = session.execute(
            text("SELECT content_norm FROM daily_hot WHERE live_date = :d"),
            {"d": live_date_str},
        ).scalars().all()
        for cn in existing:
            if cn not in keep:
                session.execute(
                    text("DELETE FROM daily_hot WHERE live_date=:d AND content_norm=:cn"),
                    {"d": live_date_str, "cn": cn},
                )

        # upsert 达标项；page_copy_cnt 不被覆盖（保留前台累计的复制数）
        for r in qualifiers:
            session.execute(
                text(
                    "INSERT INTO daily_hot(live_date, content_norm, content_sample, "
                    "send_cnt, unique_sender_cnt, first_seen, last_seen, page_copy_cnt, is_filtered) "
                    "VALUES (:d, :cn, :s, :sc, :u, :fs, :ls, 0, 0) "
                    "ON CONFLICT(live_date, content_norm) DO UPDATE SET "
                    "content_sample=excluded.content_sample, send_cnt=excluded.send_cnt, "
                    "unique_sender_cnt=excluded.unique_sender_cnt, "
                    "first_seen=excluded.first_seen, last_seen=excluded.last_seen"
                ),
                {
                    "d": live_date_str,
                    "cn": r["content_norm"],
                    "s": r["sample"],
                    "sc": r["send_cnt"],
                    "u": r["uniq"],
                    "fs": r["first_seen"],
                    "ls": r["last_seen"],
                },
            )
        session.commit()
```

> `content_raw AS sample` 是组内任意一条原文，作热梗样例足够。`text`、`datetime/timezone`、`settings_cache` 已在 cron.py import。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_cron.py::test_recount_promotes_when_threshold_met tests/test_cron.py::test_recount_skips_below_threshold tests/test_cron.py::test_recount_skips_noise -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add sb2099/cron.py tests/test_cron.py
git commit -m "feat(sb2099): recount builds daily_hot from current live-day raw"
```

---

## Task 5: 重写 archive（清 raw + daily_hot）

**Files:**
- Modify: `sb2099/cron.py`（`_archive_sync`）
- Modify: `tests/test_cron.py`（`test_archive_removes_old_rows`）

- [ ] **Step 1: 替换 `tests/test_cron.py` 的 archive 用例**

```python
def test_archive_removes_old_raw_and_daily_hot(tmp_db):
    """raw_retention_days=2（迁移后默认）：3 天前 raw 删、1 天前保留；
    daily_hot_retention_days=7：8 天前的数据日行删、今天保留。"""
    import json
    from datetime import datetime as _dt
    from sb2099.db import SessionLocal
    from sb2099.models import DailyHot, Setting

    now = datetime.utcnow().replace(microsecond=0)
    _persist_sync(_evt("recent", "u1", now - timedelta(days=1)))
    _persist_sync(_evt("old", "u2", now - timedelta(days=3)))

    today = now.date().isoformat()
    old_date = (now.date() - timedelta(days=8)).isoformat()
    with SessionLocal() as s:
        s.add(DailyHot(live_date=today, content_norm="keep", content_sample="keep",
                       send_cnt=5, unique_sender_cnt=5, first_seen=now, last_seen=now,
                       page_copy_cnt=0, is_filtered=False))
        s.add(DailyHot(live_date=old_date, content_norm="drop", content_sample="drop",
                       send_cnt=5, unique_sender_cnt=5, first_seen=now, last_seen=now,
                       page_copy_cnt=0, is_filtered=False))
        s.commit()

    removed = _archive_sync()
    assert removed == 1  # 只删了 3 天前那条 raw
    with SessionLocal() as s:
        raw_contents = [r.content_raw for r in s.execute(select(RawDanmaku)).scalars().all()]
        assert raw_contents == ["recent"]
        hot_dates = [d.live_date for d in s.execute(select(DailyHot)).scalars().all()]
        assert hot_dates == [today]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_cron.py::test_archive_removes_old_raw_and_daily_hot -v`
Expected: FAIL（旧 `_archive_sync` 不清 daily_hot；且默认 retention 行为不符）

- [ ] **Step 3: 改 `sb2099/cron.py` 的 `_archive_sync`**

```python
def _archive_sync() -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw_days = int(settings_cache.get("raw_retention_days", 2) or 2)
    raw_cutoff = now - timedelta(days=raw_days)

    hot_days = int(settings_cache.get("daily_hot_retention_days", 7) or 7)
    live_date, _ = current_live_window(now)
    hot_cutoff = (live_date - timedelta(days=hot_days)).isoformat()

    with _db.SessionLocal() as session:
        res = session.execute(delete(RawDanmaku).where(RawDanmaku.ts < raw_cutoff))
        session.execute(
            text("DELETE FROM daily_hot WHERE live_date < :c"), {"c": hot_cutoff}
        )
        session.commit()
        return int(res.rowcount or 0)
```

> `delete`、`text`、`current_live_window` 已在 Task 4 引入；确认 cron.py 顶部 `from sqlalchemy import delete, text` 存在（原文件已有 `delete, text`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_cron.py -v`
Expected: PASS（全文件 4 passed：3 recount + 1 archive）

- [ ] **Step 5: 提交**

```bash
git add sb2099/cron.py tests/test_cron.py
git commit -m "feat(sb2099): archive purges 2-day raw and 7-day daily_hot"
```

---

## Task 6: 公开读取（/api/live + /live 页）

**Files:**
- Modify: `sb2099/web/routes_api.py`（`/api/live`、import）
- Modify: `sb2099/web/routes_public.py`（`/live` 页）
- Modify: `tests/test_routes_api.py`、`tests/test_routes_public.py`

定义两段共用 SQL（day / week），两个路由都用。day 取当前数据日，week 聚合最近 7 个数据日。

- [ ] **Step 1: 在 `tests/test_routes_api.py` 加 DailyHot seed 助手并改 live 用例**

把文件顶部 `from sb2099.models import Barrage, LiveHot` 改为 `from sb2099.models import Barrage, DailyHot`。新增助手（放在文件靠前处）：

```python
def _seed_daily(content_sample, content_norm=None, *, live_date=None,
                send_cnt=10, unique=5, page_copy_cnt=0, is_filtered=False):
    """在「当前数据日」种入一条 daily_hot，返回其 id。"""
    from datetime import datetime, timezone
    from sqlalchemy import insert as sa_insert, select as sa_select
    from sb2099.db import SessionLocal
    from sb2099.live_day import current_live_window
    from sb2099.models import DailyHot
    from sb2099.normalize import normalize

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ld, _ = current_live_window(now)
    cn = content_norm or normalize(content_sample)
    with SessionLocal() as s:
        s.execute(sa_insert(DailyHot).values(
            live_date=(live_date or ld.isoformat()),
            content_norm=cn, content_sample=content_sample,
            send_cnt=send_cnt, unique_sender_cnt=unique,
            first_seen=now, last_seen=now,
            page_copy_cnt=page_copy_cnt, is_filtered=is_filtered,
        ))
        s.commit()
        return s.execute(
            sa_select(DailyHot.id).where(DailyHot.content_norm == cn)
        ).scalars().first()
```

把 `/api/live` 相关用例（约 34–90 行）改成用 `_seed_daily` 播种、断言 `data` 里 `content_sample`/`send_cnt`/`unique_senders` 字段（字段名不变）。`window=week` 用例：用 `_seed_daily(..., live_date=<今天>)` 与 `_seed_daily(..., live_date=<6天前>)` 各一条，断言两条都出现在 week 结果里。空库时 `GET /api/live?window=day` 返回 `{"window":"day","data":[]}`。

- [ ] **Step 2: 改 `tests/test_routes_public.py` 的 live 用例**

顶部 `from sb2099.models import Barrage, LiveHot` → `from sb2099.models import Barrage, DailyHot`。把 `insert(LiveHot).values(...)`（约 66 行）改为插入 DailyHot 当前数据日行（参照上面 seed 字段）。空库 `GET /live` 仍 200 且含「暂无热门弹幕」。播种一条达标行后 `GET /live?window=day` 200 且 HTML 含该 `content_sample`。

- [ ] **Step 3: 跑测试确认失败**

Run: `pytest tests/test_routes_api.py tests/test_routes_public.py -v`
Expected: FAIL（路由仍查 live_hot 表，已被删；或 import LiveHot 失败）

- [ ] **Step 4: 改 `sb2099/web/routes_api.py` 的 `/api/live`**

- 顶部 import：`from ..models import Barrage, BarrageReport, LiveHot, Tag` → 去掉 `LiveHot`（copy/promote 在 Task 7 改）。`/api/live` 用裸 text SQL，不需要模型。
- 删除 `_LIVE_WINDOWS` 字典。
- 把 `get_live` 替换为：

```python
def _live_rows(window: str):
    from datetime import datetime, timezone
    from ..live_day import current_live_window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, _ = current_live_window(now)
    if window == "day":
        sql = text(
            "SELECT id, content_sample, send_cnt, unique_sender_cnt AS unique_senders, last_seen "
            "FROM daily_hot WHERE live_date = :d AND is_filtered = 0 "
            "ORDER BY send_cnt DESC, last_seen DESC LIMIT 10"
        )
        params = {"d": live_date.isoformat()}
    else:
        from datetime import timedelta
        wk_start = (live_date - timedelta(days=6)).isoformat()
        sql = text(
            "SELECT "
            "  (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "  (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "  SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "  MAX(d.last_seen) AS last_seen "
            "FROM daily_hot d WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "GROUP BY d.content_norm ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
        )
        params = {"wk": wk_start}
    with _db.SessionLocal() as s:
        return s.execute(sql, params).mappings().all()


@router.get("/live")
def get_live(window: Literal["day", "week"] = "day") -> dict:
    rows = _live_rows(window)
    return {
        "window": window,
        "data": [
            {
                "id": r["id"],
                "content_sample": r["content_sample"],
                "send_cnt": int(r["send_cnt"] or 0),
                "unique_senders": int(r["unique_senders"] or 0),
                "last_seen": (
                    r["last_seen"].isoformat()
                    if hasattr(r["last_seen"], "isoformat")
                    else (str(r["last_seen"]) if r["last_seen"] else None)
                ),
            }
            for r in rows
        ],
    }
```

- [ ] **Step 5: 改 `sb2099/web/routes_public.py` 的 `/live` 页**

把 `live_page` 内的 SQL 段（76–91 行）替换为按 window 取 daily_hot 并 LEFT JOIN barrage 标记已入库：

```python
    from datetime import datetime, timedelta, timezone
    from ..live_day import current_live_window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, _ = current_live_window(now)
    if window == "day":
        sql = text(
            "SELECT d.id, d.content_sample, d.send_cnt, d.unique_sender_cnt AS unique_senders, "
            "d.last_seen, b.id AS barrage_id, b.tags AS barrage_tags "
            "FROM daily_hot d "
            "LEFT JOIN barrage b ON b.content_norm = d.content_norm AND b.status='active' "
            "WHERE d.live_date = :d AND d.is_filtered = 0 "
            "ORDER BY d.send_cnt DESC, d.last_seen DESC LIMIT 10"
        )
        params = {"d": live_date.isoformat()}
    else:
        wk_start = (live_date - timedelta(days=6)).isoformat()
        sql = text(
            "SELECT "
            "  (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "  d.content_norm, "
            "  (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "  SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "  MAX(d.last_seen) AS last_seen, b.id AS barrage_id, b.tags AS barrage_tags "
            "FROM daily_hot d "
            "LEFT JOIN barrage b ON b.content_norm = d.content_norm AND b.status='active' "
            "WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "GROUP BY d.content_norm ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
        )
        params = {"wk": wk_start}
    with _db.SessionLocal() as s:
        rows = s.execute(sql, params).mappings().all()
```

下方构造 `items` 的列表推导不变（字段名 id/content_sample/send_cnt/unique_senders/last_seen/barrage_id/barrage_tags 都对得上）。删除原先的 `min_unique` 读取与 `cnt_col/uniq_col` 三元组（daily_hot 已是预筛结果）。

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/test_routes_api.py tests/test_routes_public.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add sb2099/web/routes_api.py sb2099/web/routes_public.py tests/test_routes_api.py tests/test_routes_public.py
git commit -m "feat(sb2099): public live reads from daily_hot (day/week)"
```

---

## Task 7: /api/copy 与 /api/promote 指向 daily_hot

**Files:**
- Modify: `sb2099/web/routes_api.py`（`copy_one`、`promote`、import）
- Modify: `tests/test_routes_api.py`（`_seed_live_hot`、copy/promote 用例）

API 入参契约不变（`source="live_hot"`、`live_hot_id`），底层换 `DailyHot`。

- [ ] **Step 1: 改 `tests/test_routes_api.py` 的 copy/promote 播种与断言**

把 `_seed_live_hot(...)`（约 130 行）整体替换为转调 `_seed_daily`：

```python
def _seed_live_hot(content_sample="加一", content_norm=None):
    return _seed_daily(content_sample, content_norm, send_cnt=1, unique=5)
```

`test_copy_live_hot_increments`：把断言改为查 `DailyHot.page_copy_cnt`：

```python
def test_copy_live_hot_increments(client):
    hid = _seed_live_hot("某复读")
    r = client.post("/api/copy", json={"source": "live_hot", "id": hid})
    assert r.status_code == 200
    from sqlalchemy import select as sa_select
    from sb2099.db import SessionLocal
    from sb2099.models import DailyHot
    with SessionLocal() as s:
        cnt = s.execute(sa_select(DailyHot.page_copy_cnt).where(DailyHot.id == hid)).scalar_one()
        assert cnt == 1
```

promote 用例（`test_promote_*`）无需改 body（仍 `{"live_hot_id": hid, "tags":[...]}`），只要 `_seed_live_hot` 已转 daily_hot 即可。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_routes_api.py -k "copy_live_hot or promote" -v`
Expected: FAIL（handler 仍引用已删的 LiveHot 模型）

- [ ] **Step 3: 改 `sb2099/web/routes_api.py`**

- 顶部 import 改为 `from ..models import Barrage, BarrageReport, DailyHot, Tag`。
- `copy_one` 中 `source != "barrage"` 分支：把 `update(LiveHot)...page_copy_cnt=LiveHot.page_copy_cnt+1` 改为 `DailyHot`：

```python
        else:
            res = s.execute(
                update(DailyHot)
                .where(DailyHot.id == body.id)
                .values(page_copy_cnt=DailyHot.page_copy_cnt + 1)
            )
            s.commit()
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="live_hot not found")
            return {"data": {"source": "live_hot", "id": body.id}}
```

- `promote` 中 `hot = s.execute(select(LiveHot).where(LiveHot.id == body.live_hot_id))...` 改为 `DailyHot`：

```python
        hot = s.execute(
            select(DailyHot).where(DailyHot.id == body.live_hot_id)
        ).scalar_one_or_none()
        if hot is None:
            raise HTTPException(status_code=404, detail="live_hot not found")
        content = hot.content_sample
        content_norm = hot.content_norm
```

（其余 promote 逻辑、`CopyIn.source` 的 `Literal[...,"live_hot"]`、`PromoteIn.live_hot_id` 字段名都不变。）

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_routes_api.py -v`
Expected: PASS（整文件）

- [ ] **Step 5: 提交**

```bash
git add sb2099/web/routes_api.py tests/test_routes_api.py
git commit -m "feat(sb2099): copy/promote resolve against daily_hot (API contract unchanged)"
```

---

## Task 8: 后台页面（列表/详情/recompute/rescan/stats）指向 daily_hot

**Files:**
- Modify: `sb2099/web/routes_admin.py`（import + `live_hot_page` + `live_hot_detail` + `live_hot_recompute` + `live_hot_rescan` + `stats_page`）
- Modify: `sb2099/web/templates/admin/live_hot_detail.html:17`
- Modify: `tests/test_routes_admin.py`（live_hot 相关 4 个用例）

- [ ] **Step 1: 改 `tests/test_routes_admin.py` 的 live_hot 用例播种**

顶部 import：`from sb2099.models import Barrage, BarrageReport, DailyHot, RawDanmaku, Setting, Tag`（`LiveHot`→`DailyHot`）。把 4 个用例里 `insert(LiveHot).values(...)` 改为插入 daily_hot 当前数据日行。daily_hot 字段映射：原 `send_cnt_total`/`send_cnt_24h` → `send_cnt`，`unique_sender_cnt_24h` → `unique_sender_cnt`，新增 `live_date`（用 `current_live_window(datetime.utcnow()...)` 的 isoformat）、`first_seen`/`last_seen`。具体每个用例：

  - `test_live_hot_listing`：种 1 条达标行，`GET /admin/live_hot` 200 且 HTML 含 `content_sample`。
  - `test_live_hot_filtered_toggle`：种 1 条 `is_filtered=False`，`GET /admin/live_hot?filtered=true` 200（结果可为空——daily_hot 正常不含噪声，断言状态码 200 即可，删除「过滤行出现」的断言）。
  - `test_live_hot_rescan_recomputes`：种 raw + daily_hot 行后 `POST /admin/live_hot/rescan` 返回 303；改断言为「调用成功（303）且不抛错」（rescan 现在是触发一次 recount，见 Step 4）。
  - `test_live_hot_detail_lists_raw_and_top_uids`：先 `_persist_sync` 几条同内容 raw（同 content_norm），再种一条 daily_hot 行（同 content_norm），`GET /admin/live_hot/{id}` 200 且含原文/uid。

> 若某用例旧断言依赖 live_hot 专有列（如 send_cnt_total 文案），按 daily_hot 字段调整或放宽为状态码+关键文本断言。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_routes_admin.py -k live_hot -v`
Expected: FAIL（import LiveHot 失败 / 路由查已删表）

- [ ] **Step 3: 改 `sb2099/web/routes_admin.py` 列表与详情**

- 顶部 import：把 `LiveHot` 换成 `DailyHot`（其余不变）。
- `live_hot_page`（504–524）SQL 改为查 daily_hot，并把列**别名回模板期望的名字**（`send_cnt_24h`/`send_cnt_total`/`unique_sender_cnt_24h`），模板无需改：

```python
    where = "is_filtered=1" if filtered else "1=1"
    sql = text(
        "SELECT id, content_sample, send_cnt AS send_cnt_24h, send_cnt AS send_cnt_total, "
        "unique_sender_cnt AS unique_sender_cnt_24h, last_seen, is_filtered "
        f"FROM daily_hot WHERE {where} "
        "ORDER BY live_date DESC, send_cnt DESC LIMIT 200"
    )
```

- `live_hot_detail`（527–553）把 `hot = s.get(LiveHot, live_hot_id)` 改为 `hot = s.get(DailyHot, live_hot_id)`。其余（按 `hot.content_norm` 查 raw、top_uids）不变。

- [ ] **Step 4: 改 `recompute` 与 `rescan`（简化为触发 recount）**

daily_hot 由 recount 全权维护，后台两个按钮简化：

- `live_hot_recompute`（556–610）替换函数体为：重归一化 raw（仍有用，raw 留 2 天）后触发一次 recount：

```python
    from ..normalize import normalize

    _redirect_or_401(request, sb2099_admin)
    settings_cache.invalidate()
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(RawDanmaku.id, RawDanmaku.content_raw, RawDanmaku.content_norm)
        ).all()
        n_raw_updated = 0
        for rid, raw, old_norm in rows:
            new_norm = normalize(raw or "")
            if new_norm != old_norm:
                s.execute(
                    update(RawDanmaku).where(RawDanmaku.id == rid).values(content_norm=new_norm)
                )
                n_raw_updated += 1
        s.commit()
    from ..cron import _recount_sync
    _recount_sync()
    return RedirectResponse(
        url=f"/admin/live_hot?recompute_ok={n_raw_updated}_raw_renorm_rebuilt",
        status_code=303,
    )
```

- `live_hot_rescan`（613–639）替换函数体为：

```python
    _redirect_or_401(request, sb2099_admin)
    settings_cache.invalidate()
    from ..cron import _recount_sync
    _recount_sync()
    return RedirectResponse(url="/admin/live_hot?rescan_ok=recounted", status_code=303)
```

> 这样删除了对 `should_filter` 在本文件的直接 import 调用；若文件内已无其它使用，移除相关局部 import。

- [ ] **Step 5: 改 `stats_page` 计数**

`routes_admin.py:662` 把 `live_hot_total = s.execute(select(func.count(LiveHot.id))).scalar_one()` 改为：

```python
        live_hot_total = s.execute(select(func.count(DailyHot.id))).scalar_one()
```

（context key `live_hot_total` 名字保留，stats.html 不改。）

- [ ] **Step 6: 改详情模板 `admin/live_hot_detail.html:17`**

把 `累计发送数: {{ hot.send_cnt_total }} 次` 改为 `当日发送数: {{ hot.send_cnt }} 次`。其余字段（content_sample/content_norm/first_seen/last_seen/is_filtered）daily_hot 都有，不改。

- [ ] **Step 7: 跑测试确认通过**

Run: `pytest tests/test_routes_admin.py -v`
Expected: PASS（整文件）

- [ ] **Step 8: 提交**

```bash
git add sb2099/web/routes_admin.py sb2099/web/templates/admin/live_hot_detail.html tests/test_routes_admin.py
git commit -m "feat(sb2099): admin pages + stats read daily_hot; recompute/rescan trigger recount"
```

---

## Task 9: 全量回归 + VPS 部署验证

**Files:** 无代码改动（验证 + 部署）

- [ ] **Step 1: 全量测试 + 残留引用扫描**

Run: `pytest -q`
Expected: 全绿（0 failed）。

再确认无残留 `LiveHot` / `live_hot` 表引用（应只剩 API 契约字符串 `"live_hot"`、字段 `live_hot_id`、URL 路径 `/admin/live_hot`、CSS 类）：
Run: `grep -rn "LiveHot" sb2099 tests`
Expected: 无结果（模型已全部改名）。

- [ ] **Step 2: 本地起服务冒烟**

Run（后台起、打首页与 live、停）:
```powershell
$env:SB2099_ADMIN_TOKEN="localtest_" + "x"*16; $env:SB2099_IP_SALT="localtest_x"
alembic upgrade head
Start-Process -NoNewWindow uvicorn -ArgumentList "sb2099.web.app:app","--port","8099"
Start-Sleep 3
(Invoke-WebRequest http://127.0.0.1:8099/live?window=day).StatusCode
(Invoke-WebRequest http://127.0.0.1:8099/api/live?window=week).Content
Get-Process uvicorn | Stop-Process
```
Expected: `/live` 返回 200；`/api/live` 返回 `{"window":"week","data":[...]}`（空库时 data 为 []）。

- [ ] **Step 3: 提交（如有未提交的收尾）+ 推送**

```bash
git status
git push
```

- [ ] **Step 4: VPS 部署（上海阿里云 139.196.96.110，systemd: sb2099.service）**

> 部署前先备份库，再迁移、重启。命令经 `ssh aliyun-139` 执行。

```bash
ssh aliyun-139 "set -e; cd /opt/sb2099; \
  cp sb2099.db sb2099.db.bak-$(date +%Y%m%d); \
  ls -lh sb2099.db*; \
  git -C /opt/sb2099 pull 2>/dev/null || echo 'NOTE: /opt/sb2099 不是 git 仓库，需手动同步代码'"
```

若 `/opt/sb2099` 非 git 仓库：用 `scp` 或 `rsync` 同步改动后的 `sb2099/`、`alembic/versions/0005_daily_hot.py` 到 VPS（保持现有部署方式；本步按实际部署通道执行）。

```bash
ssh aliyun-139 "cd /opt/sb2099 && ./.venv/bin/alembic upgrade head && systemctl restart sb2099 && sleep 3 && systemctl is-active sb2099"
```
Expected: `active`。

- [ ] **Step 5: VPS 数据验证**

```bash
ssh aliyun-139 "cd /opt/sb2099; \
  ./.venv/bin/python -c \"import sqlite3; c=sqlite3.connect('sb2099.db'); \
  print('daily_hot rows', c.execute('select count(*) from daily_hot').fetchone()[0]); \
  print('raw rows', c.execute('select count(*) from raw_danmaku').fetchone()[0]); \
  print('settings', dict(c.execute(\\\"select key,value from setting where key in ('raw_retention_days','daily_hot_retention_days','live_hot_min_unique_senders_24h')\\\").fetchall()))\"; \
  curl -s localhost:8090/api/live?window=day | head -c 400"
```
Expected: 设置为 `raw_retention_days=2`、`daily_hot_retention_days=7`、`live_hot_min_unique_senders_24h=20`；`live_hot` 表已不存在；`/api/live` 正常返回。

- [ ] **Step 6: 次日 04:00 后回访（人工/计划）**

观察一个数据日周期：04:00 结算后 `raw_danmaku` 行数回落到 ≤2 天量、`daily_hot` 仅含达标梗、库文件大小趋稳。必要时 `VACUUM` 回收：
```bash
ssh aliyun-139 "cd /opt/sb2099 && systemctl stop sb2099 && ./.venv/bin/python -c \"import sqlite3; sqlite3.connect('sb2099.db').execute('VACUUM')\" && systemctl start sb2099 && ls -lh sb2099.db"
```

---

## 自检（Self-Review）

**Spec 覆盖**：
- raw 降 2 天缓冲 → Task 2(默认值)+Task 5(archive)。✓
- daily_hot 按日表 + ≥20 unique 入表 → Task 2(表)+Task 4(recount HAVING+threshold)。✓
- 数据日 CST 04:00 边界 → Task 1。✓
- 实时入表（recount 每分钟，频率不敏感）→ Task 4（沿用现有 60s loop，未改频率）。✓
- 04:00 仅清理 → Task 5。✓
- 今日 Top10 / 本周 Top50(累计发送量) → Task 6。✓
- 配置走 setting 表 → Task 2(迁移 UPSERT)+各处 `settings_cache.get`。✓
- 噪声不计入热梗 → Task 4(`should_filter` 过滤)。✓
- 迁移/退役 live_hot、copy/promote/admin 改读 → Task 2/7/8。✓
- 容量验证 → Task 9。✓

**占位符扫描**：无 TODO/TBD；所有代码步骤含完整代码；测试步骤含完整断言。两处「按实际调整」（normalize 输出断言、VPS 部署通道）均给了明确判定与回退，非空泛占位。

**类型一致性**：`DailyHot` 字段（`send_cnt`/`unique_sender_cnt`/`live_date`/`page_copy_cnt`）在 Task 2/4/5/6/7/8 用法一致；`current_live_window`/`live_date_of` 签名在 Task 1 定义、Task 4/5/6 调用一致；API 契约字符串 `"live_hot"`/`live_hot_id` 全程不变。
