#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
sys.path.insert(0, str(ARB))
from dataset.helius import load_slim_block  # noqa: E402

ALL = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\all_arbs_trial.jsonl")
TX = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004\tx")

slots = set()
sigs = set()
n = 0
profit = 0.0
for line in ALL.open(encoding="utf-8"):
    r = json.loads(line)
    n += 1
    profit += float(r.get("pure_profit") or 0)
    if r.get("slot") is not None:
        slots.add(int(r["slot"]))
    if r.get("signature"):
        sigs.add(r["signature"])

have_slim = 0
for s in slots:
    b = load_slim_block(s)
    if b and b.get("txs"):
        have_slim += 1

have_tx = 0
for sig in sigs:
    if (TX / sig[:2] / f"{sig}.json.gz").exists():
        have_tx += 1

print("arbs", n)
print("profit", round(profit, 1))
print("unique_slots", len(slots))
print("slim_cached", have_slim, "need", len(slots) - have_slim)
print("unique_arb_sigs", len(sigs))
print("arb_tx_cached", have_tx)
