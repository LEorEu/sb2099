"""Re-normalize all raw_danmaku.content_norm with the CURRENT normalize rules
(incl. live_suffix_strips), then clear daily_hot so it can be rebuilt from the
re-normalized raw (run tools/backfill_daily_hot.py --apply afterwards).

Use after deploying a normalize-rule change. Service should be stopped while
running so the recount loop does not aggregate half-renormalized raw.
"""
import sqlite3

from sb2099.normalize import normalize
from sb2099.ingest.aggregator import normalized_suffix_strips

DB = "/opt/sb2099/sb2099.db"

suffixes = normalized_suffix_strips()
print("suffixes:", suffixes)

c = sqlite3.connect(DB)
rows = c.execute("SELECT id, content_raw, content_norm FROM raw_danmaku").fetchall()
upd = 0
for rid, raw, old in rows:
    new = normalize(raw or "", suffixes=suffixes)
    if new and new != old:
        c.execute("UPDATE raw_danmaku SET content_norm=? WHERE id=?", (new, rid))
        upd += 1
c.execute("DELETE FROM daily_hot")
c.commit()
print(f"re-normalized {upd}/{len(rows)} raw rows; daily_hot cleared")
c.close()
