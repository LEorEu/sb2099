"""One-off backfill: rebuild daily_hot from existing raw_danmaku for the most
recent N broadcast days (daily_hot_retention_days), so the weekly board works
right after the live_hot -> daily_hot migration, before the 04:00 archive prunes
old raw. Dry-run by default; pass --apply to write.

Broadcast day = CST 04:00 -> next 04:00. ts is stored UTC-naive, so
live_date = date(ts + 4 hours) (UTC+8 then back 4h == +4h on the UTC value).
"""
import sys
import sqlite3

from sb2099.ingest.aggregator import should_filter
from sb2099.settings import settings_cache

DB = "/opt/sb2099/sb2099.db"
APPLY = "--apply" in sys.argv

thr = int(settings_cache.get("live_hot_min_unique_senders_24h", 20) or 20)
hot_days = int(settings_cache.get("daily_hot_retention_days", 7) or 7)

c = sqlite3.connect(DB)
all_dates = [r[0] for r in c.execute(
    "SELECT DISTINCT date(ts,'+4 hours') ld FROM raw_danmaku ORDER BY ld DESC"
)]
target = all_dates[:hot_days]
print(f"threshold={thr} hot_days={hot_days}")
print(f"target live_dates: {target}")

total = 0
for ld in target:
    rows = c.execute(
        "SELECT content_norm, COUNT(*) sc, COUNT(DISTINCT uid) u, MIN(ts) fs, MAX(ts) ls, "
        "(SELECT content_raw FROM raw_danmaku r2 "
        " WHERE r2.content_norm=r1.content_norm AND date(r2.ts,'+4 hours')=? "
        " ORDER BY length(content_raw) LIMIT 1) sample "
        "FROM raw_danmaku r1 WHERE date(ts,'+4 hours')=? "
        "GROUP BY content_norm HAVING COUNT(DISTINCT uid) >= ?",
        (ld, ld, thr),
    ).fetchall()
    kept = [r for r in rows if not should_filter(r[0])]
    print(f"  {ld}: candidates>=thr={len(rows):>3}  kept(non-noise)={len(kept):>3}")
    if APPLY:
        for cn, sc, u, fs, ls, sample in kept:
            c.execute(
                "INSERT INTO daily_hot(live_date,content_norm,content_sample,send_cnt,"
                "unique_sender_cnt,first_seen,last_seen,page_copy_cnt,is_filtered) "
                "VALUES (?,?,?,?,?,?,?,0,0) "
                "ON CONFLICT(live_date,content_norm) DO UPDATE SET "
                "content_sample=excluded.content_sample, send_cnt=excluded.send_cnt, "
                "unique_sender_cnt=excluded.unique_sender_cnt, "
                "first_seen=excluded.first_seen, last_seen=excluded.last_seen",
                (ld, cn, sample, sc, u, fs, ls),
            )
            total += 1

if APPLY:
    c.commit()
    print(f"UPSERTED {total} rows; daily_hot total now "
          f"{c.execute('SELECT COUNT(*) FROM daily_hot').fetchone()[0]}")
else:
    print("(dry run; pass --apply to write)")
c.close()
