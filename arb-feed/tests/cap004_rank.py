#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

P = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\all_arbs_trial.jsonl")
by = defaultdict(lambda: {"n": 0, "profit": 0.0, "hops2": 0, "dlmm_pump": 0, "slots": set()})
n = 0
for line in P.open(encoding="utf-8"):
    r = json.loads(line)
    n += 1
    u = r.get("user") or "?"
    b = by[u]
    b["n"] += 1
    b["profit"] += float(r.get("pure_profit") or 0)
    if r.get("number_of_swap_steps") == 2:
        b["hops2"] += 1
    if tuple(r.get("dexes") or []) == ("Meteora DLMM", "Pump Swap"):
        b["dlmm_pump"] += 1
    if r.get("slot") is not None:
        b["slots"].add(int(r["slot"]))
print("total", n, "searchers", len(by))
rows = sorted(by.items(), key=lambda kv: -kv[1]["profit"])
print("rank user n profit hops2 dlmm_pump slots")
for i, (u, b) in enumerate(rows[:15], 1):
    print(i, u, b["n"], round(b["profit"], 1), b["hops2"], b["dlmm_pump"], len(b["slots"]))
