#!/usr/bin/env python3
import json
from pathlib import Path
p = Path("/home/louis/arb-cap/exec_live002b/report.json")
r = json.loads(p.read_text())
sim = r.get("simulate") or {}
print("err", sim.get("err"))
print("cu", sim.get("cu"))
print("tx_len", r.get("tx_len"), "margin", r.get("margin"))
print("fee_recipient", r.get("fee_recipient"))
print("fee_recipient_quote", r.get("fee_recipient_quote"))
print("alt", r.get("alt"))
print("--- logs ---")
for line in sim.get("logs") or []:
    print(line)
