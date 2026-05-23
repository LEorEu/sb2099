"""一次性维护脚本：从现有 raw_danmaku 重建 live_hot。

何时用：
- 历史 raw_danmaku 早于 aggregator 引入 live_hot upsert（如 0.1.0 初始 commit）
- live_hot 表被误清，需要从 raw 恢复
- 改了 noise_filters 想全量重扫 is_filtered

幂等：先清空 live_hot 再重建。raw_danmaku 不受影响。
"""
from __future__ import annotations

from sqlalchemy import delete, select, text

from sb2099 import db as _db
from sb2099.models import LiveHot, RawDanmaku
from sb2099.settings import settings_cache


def backfill() -> int:
    filters = settings_cache.get("live_noise_filters", []) or []

    with _db.SessionLocal() as session:
        session.execute(delete(LiveHot))

        # 聚合 raw_danmaku → 每个 content_norm 一行
        session.execute(
            text(
                """
                INSERT INTO live_hot (
                    content_norm, content_sample, first_seen, last_seen,
                    page_copy_cnt, send_cnt_24h, send_cnt_7d, send_cnt_total,
                    unique_sender_cnt_24h, unique_sender_cnt_7d, is_filtered
                )
                SELECT
                    content_norm,
                    (
                        SELECT content_raw FROM raw_danmaku r2
                        WHERE r2.content_norm = r1.content_norm
                        ORDER BY ts ASC LIMIT 1
                    ) AS content_sample,
                    MIN(ts), MAX(ts),
                    0, 0, 0, COUNT(*),
                    0, 0, 0
                FROM raw_danmaku r1
                GROUP BY content_norm
                """
            )
        )

        # 重算 is_filtered：扫描该 content_norm 下任一 raw 是否命中 filter 子串
        if filters:
            rows = session.execute(select(LiveHot.id, LiveHot.content_norm)).all()
            for hot_id, cn in rows:
                hit = session.execute(
                    select(RawDanmaku.content_raw).where(RawDanmaku.content_norm == cn)
                ).scalars().all()
                if any(any(kw in r for kw in filters) for r in hit):
                    session.execute(
                        text("UPDATE live_hot SET is_filtered=1 WHERE id=:id"),
                        {"id": hot_id},
                    )

        session.commit()
        return session.execute(select(LiveHot)).scalars().all().__len__()


if __name__ == "__main__":
    n = backfill()
    print(f"backfilled live_hot: {n} rows")
