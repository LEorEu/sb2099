"""add user roster table

Revision ID: 0007_user
Revises: 0006_live_suffix_strips
Create Date: 2026-05-29
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_user"
down_revision: str | None = "0006_live_suffix_strips"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("uid", sa.Text(), primary_key=True),
        sa.Column("nickname", sa.Text(), nullable=True),
        sa.Column("avatar", sa.Text(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="seed"),
    )
    op.create_index("ix_user_last_seen", "user", ["last_seen"])
    op.create_index("ix_user_nickname", "user", ["nickname"])


def downgrade() -> None:
    op.drop_index("ix_user_nickname", table_name="user")
    op.drop_index("ix_user_last_seen", table_name="user")
    op.drop_table("user")
