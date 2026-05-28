"""seed live_hot_max_length setting (default 80)

Revision ID: 0004_add_live_hot_max_length
Revises: 0003_add_live_hot_min_length
Create Date: 2026-05-28
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_live_hot_max_length"
down_revision: str | None = "0003_add_live_hot_min_length"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT OR IGNORE INTO setting(key, value, updated_at) "
            "VALUES (:k, :v, :u)"
        ),
        {"k": "live_hot_max_length", "v": json.dumps(80), "u": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM setting WHERE key='live_hot_max_length'"))
