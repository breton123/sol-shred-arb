#!/usr/bin/env python3
"""All-arb book shape (no headroom). Not the shred-competable surface."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ALL = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\all_arbs_trial.jsonl")
HOURS = 11913.749 / 3600.0
MRIYA = "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X"
BQ = "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK"
DTVM = "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx"

n = 0
profit = 0.0
by_route = defaultdict(lambda: [0, 0.0])
by_slot = defaultdict(list)
fat = []
for line in ALL.open(encoding="utf-8"):
    r = json.loads(line)
    n += 1
    p = float(r.get("pure_profit") or 0)
    profit += p
    route = " -> ".join(r.get("dexes") or [])
    by_route[route][0] += 1
    by_route[route][1] += p
    slot = r.get("slot")
    if slot is not None:
        by_slot[int(slot)].append(r)
    if p >= 10:
        fat.append(r)

print(f"arbs {n}  ${profit:.1f}  ${profit/HOURS:.1f}/hr  hours={HOURS:.3f}")
print("TOP ROUTES")
for route, (c, dol) in sorted(by_route.items(), key=lambda kv: -kv[1][1])[:15]:
    print(f"  {dol:8.1f}  {c:6}  {route}")

print("FAT n>=10", len(fat), "slots", len({int(r['slot']) for r in fat if r.get('slot') is not None}))
for thr in (10, 25, 50, 100, 250, 500, 1000):
    xs = [r for r in fat if float(r.get("pure_profit") or 0) >= thr]
    print(f"  >=${thr}: n={len(xs)} ${sum(float(r.get('pure_profit') or 0) for r in xs):.1f} slots={len({int(r['slot']) for r in xs if r.get('slot')})}")

# slot occupancy (NOT trigger groups)
occ = Counter(len({x.get('user') for x in xs}) for xs in by_slot.values())
print("searchers per slot (not per trigger)")
for k in sorted(occ)[:12]:
    print(f"  {k}: {occ[k]} slots")

no_m = no_mb = no_mbd = 0
pm = pb = pd = 0.0
for xs in by_slot.values():
    users = {x.get("user") for x in xs}
    dol = sum(float(x.get("pure_profit") or 0) for x in xs)
    if MRIYA not in users:
        no_m += 1
        pm += dol
    if MRIYA not in users and BQ not in users:
        no_mb += 1
        pb += dol
    if MRIYA not in users and BQ not in users and DTVM not in users:
        no_mbd += 1
        pd += dol
print(f"slots no Mriya: {no_m} ${pm:.1f}")
print(f"slots no Mriya/4BQ: {no_mb} ${pb:.1f}")
print(f"slots no Mriya/4BQ/Dtvm: {no_mbd} ${pd:.1f}")
