#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path

rows = [json.loads(l) for l in Path("hist_funnel.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
late = [r for r in rows if r["cohort"] == "late121"]
by = defaultdict(lambda: [0, 0.0])
for r in late:
    by[r["frame"] + " " + r["frame_why"]][0] += 1
    by[r["frame"] + " " + r["frame_why"]][1] += r["profit"]
print("LATE DOLLARS")
for k, (n, usd) in sorted(by.items(), key=lambda kv: -kv[1][1]):
    print(f"  {k:<28} {n:4} ${usd:8.1f}")

print("KNOWN / ROUTE0")
for r in late:
    if r["pool_known"] or r["route"]:
        print(f"  ${r['profit']:.2f} route={r['route']} pool={r['route_pool']}")

print("JACKPOTS")
for r in sorted(rows, key=lambda r: -r["profit"]):
    if r["profit"] < 50:
        break
    print(f"  ${r['profit']:7.1f} {r['frame_why']:<18} known={r['pool_known']} route={r['route']} cohort={r['cohort']}")

mev = json.loads(Path("mev_hour.json").read_text(encoding="utf-8"))
ours = json.loads(Path("our_slots.json").read_text(encoding="utf-8")) if Path("our_slots.json").exists() else []
their = set(mev["dlmm_pump_slots"])
our = set(ours)
print("slot overlap", len(their & our), "of", len(their), "dlmm/pump slots; our slots", len(our))
