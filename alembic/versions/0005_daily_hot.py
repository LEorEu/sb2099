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
