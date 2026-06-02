"""seed live_cut_markers setting（截断标记：从标记处砍掉 douyuex 整条装饰尾巴）

Revision ID: 0011_live_cut_markers
Revises: 0010_submit_signed_ratelimit
Create Date: 2026-06-02
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_live_cut_markers"
down_revision: str | None = "0010_submit_signed_ratelimit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT OR IGNORE INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
        {"k": "live_cut_markers", "v": json.dumps(["Oᴗoಣ"], ensure_ascii=False), "u": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM setting WHERE key='live_cut_markers'"))
