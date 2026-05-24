"""barrage_fts switch to trigram tokenizer for CJK substring search

Revision ID: 0002_fts5_trigram
Revises: 0001_init
Create Date: 2026-05-24

unicode61 把连续 CJK 字符当一个 token，导致搜 "草" 不命中 "草草草"。
trigram 把每串切成 3 字 n-gram，substring 风格匹配（含 CJK）。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_fts5_trigram"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 删触发器 + 虚表
    op.execute("DROP TRIGGER IF EXISTS barrage_au")
    op.execute("DROP TRIGGER IF EXISTS barrage_ad")
    op.execute("DROP TRIGGER IF EXISTS barrage_ai")
    op.execute("DROP TABLE IF EXISTS barrage_fts")

    # 用 trigram 重建
    op.execute(
        "CREATE VIRTUAL TABLE barrage_fts USING fts5("
        "content, content_norm UNINDEXED, "
        "content='barrage', content_rowid='id', "
        "tokenize='trigram')"
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

    # 既有数据需重灌索引
    op.execute(
        "INSERT INTO barrage_fts(rowid, content, content_norm) "
        "SELECT id, content, content_norm FROM barrage"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS barrage_au")
    op.execute("DROP TRIGGER IF EXISTS barrage_ad")
    op.execute("DROP TRIGGER IF EXISTS barrage_ai")
    op.execute("DROP TABLE IF EXISTS barrage_fts")
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
    op.execute(
        "INSERT INTO barrage_fts(rowid, content, content_norm) "
        "SELECT id, content, content_norm FROM barrage"
    )
