"""initial schema: 6 tables + barrage_fts + triggers + seed tags & settings

Revision ID: 0001_init
Revises:
Create Date: 2026-05-23
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Sequence

import sqlalchemy as sa
from alembic import op

from sb2099.config import DEFAULTS, INITIAL_TAGS

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "raw_danmaku",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("uid", sa.Text()),
        sa.Column("nickname", sa.Text()),
        sa.Column("content_raw", sa.Text(), nullable=False),
        sa.Column("content_norm", sa.Text(), nullable=False),
    )
    op.create_index("ix_raw_norm_ts", "raw_danmaku", ["content_norm", "ts"])
    op.create_index("ix_raw_ts", "raw_danmaku", ["ts"])

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
        sa.Column("is_filtered", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_livehot_send24h", "live_hot", ["send_cnt_24h"])
    op.create_index("ix_livehot_send7d", "live_hot", ["send_cnt_7d"])
    op.create_index("ix_livehot_copy", "live_hot", ["page_copy_cnt"])
    op.create_index("ix_livehot_lastseen", "live_hot", ["last_seen"])

    op.create_table(
        "barrage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_norm", sa.Text(), nullable=False, unique=True),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="user"),
        sa.Column("submitter_ip_hash", sa.String(length=32)),
        sa.Column("submit_time", sa.DateTime(), nullable=False),
        sa.Column("cnt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_cnt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.create_index("ix_barrage_submit", "barrage", ["submit_time"])
    op.create_index("ix_barrage_cnt", "barrage", ["cnt"])
    op.create_index("ix_barrage_status_submit", "barrage", ["status", "submit_time"])

    op.create_table(
        "tag",
        sa.Column("value", sa.String(length=8), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("icon_url", sa.Text()),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    op.create_table(
        "barrage_report",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("barrage_id", sa.Integer(), nullable=False),
        sa.Column("ip_hash", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("barrage_id", "ip_hash", name="uq_report_barrage_ip"),
    )
    op.create_index("ix_report_barrage_ip", "barrage_report", ["barrage_id", "ip_hash"])

    op.create_table(
        "setting",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # FTS5 虚拟表 + 同步触发器
    op.execute(
        "CREATE VIRTUAL TABLE barrage_fts USING fts5("
        "content, content_norm UNINDEXED, "
        "content='barrage', content_rowid='id', "
        "tokenize='unicode61 remove_diacritics 2')"
    )
    op.execute(
        "CREATE TRIGGER barrage_ai AFTER INSERT ON barrage BEGIN "
        "INSERT INTO barrage_fts(rowid, content, content_norm) "
        "VALUES (new.id, new.content, new.content_norm); END"
    )
    op.execute(
        "CREATE TRIGGER barrage_ad AFTER DELETE ON barrage BEGIN "
        "INSERT INTO barrage_fts(barrage_fts, rowid, content, content_norm) "
        "VALUES('delete', old.id, old.content, old.content_norm); END"
    )
    op.execute(
        "CREATE TRIGGER barrage_au AFTER UPDATE ON barrage BEGIN "
        "INSERT INTO barrage_fts(barrage_fts, rowid, content, content_norm) "
        "VALUES('delete', old.id, old.content, old.content_norm); "
        "INSERT INTO barrage_fts(rowid, content, content_norm) "
        "VALUES (new.id, new.content, new.content_norm); END"
    )

    # 种子数据
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bind = op.get_bind()
    for tag in INITIAL_TAGS:
        bind.execute(
            sa.text(
                "INSERT INTO tag(value, label, icon_url, sort, enabled) "
                "VALUES (:value, :label, :icon_url, :sort, :enabled)"
            ),
            tag,
        )
    for key, val in DEFAULTS.items():
        bind.execute(
            sa.text("INSERT INTO setting(key, value, updated_at) VALUES (:k, :v, :u)"),
            {"k": key, "v": json.dumps(val, ensure_ascii=False), "u": now},
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS barrage_au")
    op.execute("DROP TRIGGER IF EXISTS barrage_ad")
    op.execute("DROP TRIGGER IF EXISTS barrage_ai")
    op.execute("DROP TABLE IF EXISTS barrage_fts")
    op.drop_table("setting")
    op.drop_table("barrage_report")
    op.drop_table("tag")
    op.drop_table("barrage")
    op.drop_table("live_hot")
    op.drop_table("raw_danmaku")
