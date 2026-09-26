#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
sys.path.insert(0, str(ARB))
from dataset.helius import load_slim_block  # noqa: E402

ALL = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\all_arbs_trial.jsonl")
have = miss = 0
slots_have = set()
slots_miss = set()
n = 0
dol_h = dol_m = 0.0
for line in ALL.open(encoding="utf-8"):
    r = json.loads(line)
    p = float(r.get("pure_profit") or 0)
    if p < 10 or r.get("slot") is None:
        continue
    n += 1
    s = int(r["slot"])
    b = load_slim_block(s)
    if b and b.get("txs"):
        have += 1
        dol_h += p
        slots_have.add(s)
    else:
        miss += 1
        dol_m += p
        slots_miss.add(s)
print("fat>=$10 arbs", n, "have_slim", have, f"${dol_h:.1f}", "miss", miss, f"${dol_m:.1f}")
print("slots have", len(slots_have), "miss", len(slots_miss))
