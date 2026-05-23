"""ORM 模型（与 alembic 0001 迁移对齐）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawDanmaku(Base):
    __tablename__ = "raw_danmaku"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    uid: Mapped[str | None] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(Text)
    content_raw: Mapped[str] = mapped_column(Text, nullable=False)
    content_norm: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_raw_norm_ts", "content_norm", "ts"),
        Index("ix_raw_ts", "ts"),
    )


class LiveHot(Base):
    __tablename__ = "live_hot"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_norm: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    content_sample: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    page_copy_cnt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    send_cnt_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    send_cnt_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    send_cnt_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_sender_cnt_24h: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_sender_cnt_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_filtered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_livehot_send24h", "send_cnt_24h"),
        Index("ix_livehot_send7d", "send_cnt_7d"),
        Index("ix_livehot_copy", "page_copy_cnt"),
        Index("ix_livehot_lastseen", "last_seen"),
    )


class Barrage(Base):
    __tablename__ = "barrage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_norm: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    submitter_ip_hash: Mapped[str | None] = mapped_column(String(32))
    submit_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cnt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_cnt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    __table_args__ = (
        Index("ix_barrage_submit", "submit_time"),
        Index("ix_barrage_cnt", "cnt"),
        Index("ix_barrage_status_submit", "status", "submit_time"),
    )


class Tag(Base):
    __tablename__ = "tag"
    value: Mapped[str] = mapped_column(String(8), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    icon_url: Mapped[str | None] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BarrageReport(Base):
    __tablename__ = "barrage_report"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    barrage_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("barrage_id", "ip_hash", name="uq_report_barrage_ip"),
        Index("ix_report_barrage_ip", "barrage_id", "ip_hash"),
    )


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
