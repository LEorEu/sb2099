"""seed live_suffix_strips setting (douyuex 自定义尾缀剥除表)

Revision ID: 0006_live_suffix_strips
Revises: 0005_daily_hot
Create Date: 2026-05-29
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_live_suffix_strips"
down_revision: str | None = "0005_daily_hot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    # 既有库新增该 key;已存在则不动(管理员可能已在后台配过)
    bind.execute(
        sa.text("INSERT OR IGNORE INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
        {"k": "live_suffix_strips", "v": json.dumps(["喵", "Oᴗoಣ"], ensure_ascii=False), "u": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM setting WHERE key='live_suffix_strips'"))
