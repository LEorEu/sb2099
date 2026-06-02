"""seed ratelimit_submit_signed_per_hour_per_ip（已署名用户更宽松的投稿限额）

Revision ID: 0010_submit_signed_ratelimit
Revises: 0009_tag_voting
Create Date: 2026-06-02
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_submit_signed_ratelimit"
down_revision: str | None = "0009_tag_voting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    # 既有库新增该 key；已存在则不动（管理员可能已配过）
    bind.execute(
        sa.text("INSERT OR IGNORE INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
        {"k": "ratelimit_submit_signed_per_hour_per_ip", "v": json.dumps(30), "u": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM setting WHERE key='ratelimit_submit_signed_per_hour_per_ip'"))
