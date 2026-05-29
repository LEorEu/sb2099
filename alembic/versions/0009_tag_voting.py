"""barrage_tag_vote 表 + Tag 加 proposer 字段 + tag_vote_threshold 默认值

Revision ID: 0009_tag_voting
Revises: 0008_submitter_uid_and_review
Create Date: 2026-05-30
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_tag_voting"
down_revision: str | None = "0008_submitter_uid_and_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DEFAULTS: dict[str, object] = {
    "tag_vote_threshold": 3,
}


def upgrade() -> None:
    op.create_table(
        "barrage_tag_vote",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("barrage_id", sa.Integer(), nullable=False),
        sa.Column("tag_value", sa.String(8), nullable=False),
        sa.Column("voter_uid", sa.Text(), nullable=True),
        sa.Column("voter_ip_hash", sa.String(32), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
    )
    # 同 uid 对同 (barrage, tag) 只能投一次（uid 为 NULL 时退化到下方 IP 索引）
    op.create_index(
        "uq_vote_uid",
        "barrage_tag_vote",
        ["barrage_id", "tag_value", "voter_uid"],
        unique=True,
        sqlite_where=sa.text("voter_uid IS NOT NULL"),
    )
    # 匿名（无 uid）路径：同 IP hash 对同 (barrage, tag) 只能投一次
    op.create_index(
        "uq_vote_ip",
        "barrage_tag_vote",
        ["barrage_id", "tag_value", "voter_ip_hash"],
        unique=True,
        sqlite_where=sa.text("voter_uid IS NULL"),
    )
    op.create_index("ix_vote_barrage_tag", "barrage_tag_vote", ["barrage_id", "tag_value"])

    with op.batch_alter_table("tag") as batch:
        batch.add_column(sa.Column("proposer_uid", sa.Text(), nullable=True))
        batch.add_column(sa.Column("proposer_ip_hash", sa.String(32), nullable=True))
        batch.add_column(sa.Column("proposed_at", sa.DateTime(), nullable=True))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    for k, v in _DEFAULTS.items():
        bind.execute(
            sa.text("INSERT OR IGNORE INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
            {"k": k, "v": json.dumps(v), "u": now},
        )


def downgrade() -> None:
    bind = op.get_bind()
    for k in _DEFAULTS:
        bind.execute(sa.text("DELETE FROM setting WHERE key=:k"), {"k": k})
    with op.batch_alter_table("tag") as batch:
        batch.drop_column("proposed_at")
        batch.drop_column("proposer_ip_hash")
        batch.drop_column("proposer_uid")
    op.drop_index("ix_vote_barrage_tag", table_name="barrage_tag_vote")
    op.drop_index("uq_vote_ip", table_name="barrage_tag_vote")
    op.drop_index("uq_vote_uid", table_name="barrage_tag_vote")
    op.drop_table("barrage_tag_vote")
