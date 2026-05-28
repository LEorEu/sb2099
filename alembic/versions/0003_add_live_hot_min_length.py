"""seed live_hot_min_length setting (default 2)

Revision ID: 0003_add_live_hot_min_length
Revises: 0002_fts5_trigram
Create Date: 2026-05-28
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_live_hot_min_length"
down_revision: str | None = "0002_fts5_trigram"
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
        {"k": "live_hot_min_length", "v": json.dumps(2), "u": now},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM setting WHERE key='live_hot_min_length'"))
