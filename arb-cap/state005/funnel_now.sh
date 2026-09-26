#!/bin/bash
echo "=== oneshot ==="
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_MISSING
echo "=== paper ==="
grep -E 'funnel|PAPER-ORBIT  up=' /home/louis/captures/paper_orbit/paper_state006.log | tail -n 6
echo "=== lifetime ==="
python3 /home/louis/arb-cap/state005/lifetime_funnel.py
echo "=== windowed ==="
python3 /home/louis/arb-cap/state005/agg_funnel.py
echo "=== last gates ==="
python3 - <<'PY'
import json
from pathlib import Path
from collections import Counter
c = Counter()
n = 0
last = []
with Path("/home/louis/captures/paper_orbit/opp_synced.jsonl").open() as f:
    for line in f:
        if '"kind":"gate"' not in line:
            continue
        rec = json.loads(line)
        n += 1
        key = (
            "k" if rec.get("known") else "u",
            "s" if rec.get("searchable") else "-",
            "c" if rec.get("cap_hurdle") else "-",
            "y" if rec.get("synced_all") else "-",
            "a" if rec.get("age32_all") else "-",
            "m" if rec.get("mut_ok_all") else "-",
            rec.get("seq") or "",
        )
        c[key] += 1
        last.append(rec)
print("gate_n", n)
print("pattern known/search/cap/sync/age32/mut/seq")
for k, v in c.most_common(12):
    print(v, k)
print("--- last 5 searchable ---")
for r in [x for x in last if x.get("searchable")][-5:]:
    print({k: r.get(k) for k in (
        "seq","cap_gross","cap_hurdle","n_hop","n_sync","synced_all",
        "age_max","age32_all","mut_ok_all","exec_fam")})
PY
