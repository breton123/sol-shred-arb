#!/bin/bash
echo "=== pids ==="
pgrep -a -f 'state005/state006.py|oneshot_live.py|build/paper_orbit' || true
echo "=== armed ==="
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_MISSING
echo "=== state006 ==="
tail -n 12 /home/louis/captures/paper_orbit/state006.log
echo "=== paper funnel ==="
grep -E 'funnel|SEARCHABLE|pools=' /home/louis/captures/paper_orbit/paper_state006.log | tail -n 8
echo "=== newest searchable ==="
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
rows = []
with p.open("r", encoding="utf-8", errors="replace") as f:
    for line in f:
        if '"opp_searchable"' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("kind") == "opp_searchable":
            rows.append(rec)
print("total", len(rows))
fresh = [r for r in rows if (r.get("fresh") or {}).get("ok")]
print("fresh_any", len(fresh))
print("--- last 8 ---")
for r in rows[-8:]:
    fr = r.get("fresh") or {}
    print(
        r.get("seq") or r.get("bucket"),
        "cap_ok", r.get("cap_ok"),
        "cap_g", r.get("cap_gross"),
        "fresh", fr.get("ok"),
        "age", fr.get("age_slots"),
        "auth", fr.get("auth"),
        "shred", fr.get("shred"),
        "sendable", fr.get("sendable"),
    )
PY
echo "=== agg ==="
python3 /home/louis/arb-cap/state005/agg_searchable.py
