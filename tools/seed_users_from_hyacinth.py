"""One-off seed: 从 hyacinth_sentry 的 events.db 把活跃用户名册导入 sb2099 的 user 表。

uid -> 最新昵称 + 头像(ic 路径)。源库以只读方式打开，绝不写入。
Dry-run 默认；加 --apply 才落库。可重复运行(ON CONFLICT 更新昵称/头像/last_seen)。

  python -m tools.seed_users_from_hyacinth                       # 预览(默认源 /opt/hyacinth_sentry/events.db)
  python -m tools.seed_users_from_hyacinth --apply               # 落库
  python -m tools.seed_users_from_hyacinth --src ./events.db --apply
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from sb2099 import db as _db
from sb2099.models import User
from sb2099.users import avatar_url, build_roster

DEFAULT_SRC = "/opt/hyacinth_sentry/events.db"


def _ms_to_naive_utc(ms: int) -> datetime:
    """epoch ms → UTC naive datetime(与 sb2099 其余表的时间存法一致)。"""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=DEFAULT_SRC, help="hyacinth events.db 路径")
    ap.add_argument("--apply", action="store_true", help="真正写入(否则只预览)")
    args = ap.parse_args()

    src = sqlite3.connect(f"file:{args.src}?mode=ro", uri=True)
    try:
        rows = src.execute(
            "SELECT uid, nickname, raw, ts FROM events "
            "WHERE uid IS NOT NULL AND uid != ''"
        ).fetchall()
    finally:
        src.close()

    roster = build_roster(rows)
    with_avatar = sum(1 for v in roster.values() if v["avatar"])
    with_nick = sum(1 for v in roster.values() if v["nickname"])
    print(f"source rows:   {len(rows)}")
    print(f"distinct uids: {len(roster)}")
    print(f"with nickname: {with_nick}")
    print(f"with avatar:   {with_avatar}")

    if not args.apply:
        print("\n--- 前 5 条预览 ---")
        for uid, v in list(roster.items())[:5]:
            print(f"  {uid}  {v['nickname']!r}  {avatar_url(v['avatar'])}")
        print("\n(dry run; 加 --apply 才写入)")
        return

    n = 0
    with _db.SessionLocal() as session:
        for uid, v in roster.items():
            last_seen = _ms_to_naive_utc(v["last_seen_ms"])
            session.execute(
                sqlite_insert(User)
                .values(
                    uid=uid,
                    nickname=v["nickname"],
                    avatar=v["avatar"],
                    first_seen=_ms_to_naive_utc(v["first_seen_ms"]),
                    last_seen=last_seen,
                    source="seed",
                )
                .on_conflict_do_update(
                    index_elements=["uid"],
                    set_={
                        "nickname": v["nickname"],
                        "avatar": v["avatar"],
                        "last_seen": last_seen,
                    },
                )
            )
            n += 1
        session.commit()
        total = session.query(User).count()
    print(f"upserted {n} users; user 表当前共 {total} 条")


if __name__ == "__main__":
    main()
