#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
n = 0
for line in p.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    n += 1
    if n > 8:
        break
    a = r.get("arb") or {}
    print(
        f"{n} ver={r.get('state_version_before')} idx={r.get('n',{}).get('pool_idx')} "
        f"auth={r.get('auth_slot')} ain={a.get('amount_in')} "
        f"mid={a.get('intermediate')} fin={a.get('final')} gp={a.get('gross')} "
        f"dec_ns={r.get('timing',{}).get('decision_ns')}"
    )
print("total_lines", sum(1 for x in p.read_text().splitlines() if x.strip()))
