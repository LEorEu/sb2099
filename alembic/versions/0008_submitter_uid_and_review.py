"""barrage: 新增 submitter_uid + review_reason + 防伪 setting 默认值

Revision ID: 0008_submitter_uid_and_review
Revises: 0007_user
Create Date: 2026-05-29
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_submitter_uid_and_review"
down_revision: str | None = "0007_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ANTI_FRAUD_DEFAULTS: dict[str, object] = {
    "submission_anti_fraud_enabled": True,
    "submission_uid_multi_ip_window_days": 7,
    "submission_uid_multi_ip_threshold": 5,
    "submission_uid_inactive_days": 30,
    "submission_uid_unseen_blocks": True,
    "submission_withdraw_window_seconds": 60,
}


def upgrade() -> None:
    with op.batch_alter_table("barrage") as batch:
        batch.add_column(sa.Column("submitter_uid", sa.Text(), nullable=True))
        batch.add_column(sa.Column("review_reason", sa.Text(), nullable=True))
    op.create_index(
        "ix_barrage_submitter",
        "barrage",
        ["submitter_uid"],
        sqlite_where=sa.text("submitter_uid IS NOT NULL"),
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    for k, v in _ANTI_FRAUD_DEFAULTS.items():
        bind.execute(
            sa.text("INSERT OR IGNORE INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
            {"k": k, "v": json.dumps(v), "u": now},
        )


def downgrade() -> None:
    op.drop_index("ix_barrage_submitter", table_name="barrage")
    with op.batch_alter_table("barrage") as batch:
        batch.drop_column("review_reason")
        batch.drop_column("submitter_uid")
    bind = op.get_bind()
    for k in _ANTI_FRAUD_DEFAULTS:
        bind.execute(sa.text("DELETE FROM setting WHERE key=:k"), {"k": k})
