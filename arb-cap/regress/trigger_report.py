#!/usr/bin/env python3
import json
import sys
from collections import defaultdict
from pathlib import Path

import trigger_outer as t

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
names = t.load_names()
rows = [json.loads(l) for l in Path("trigger_outer.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

def full_primary(r):
    if not r.get("pred_sig"):
        return "(no predecessor)"
    tx = t.load_tx(r["pred_sig"])
    info = t.analyze_tx(tx, names)
    ids = [p for p in (info.get("outer_ids") or []) if p not in t.INFRA]
    if not ids:
        return "(infra only)"
    def lab(pid):
        if pid in names:
            return names[pid][0]
        return pid
    if len(ids) == 1:
        return lab(ids[0])
    return " + ".join(lab(p) for p in ids)

for r in rows:
    r["full"] = full_primary(r)

def emit(title, subset):
    acc = defaultdict(lambda: [0, 0.0])
    for r in subset:
        acc[r["full"]][0] += 1
        acc[r["full"]][1] += r["profit"]
    print(f"\n{title}  n={len(subset)}  ${sum(r['profit'] for r in subset):.1f}")
    print(f"{'outer program':<52} {'races':>6} {'$':>10}")
    for name, (n, usd) in sorted(acc.items(), key=lambda kv: -kv[1][1]):
        print(f"{name:<52} {n:6} {usd:10.1f}")

late = [r for r in rows if r["cohort"] == "late121"]
nodex = [r for r in late if r["frame_why"] == "no_dex_bytes"]
jack = [r for r in rows if r["profit"] >= 50]
emit("LATE 121 outer program", late)
emit("NO-DEX-BYTES bucket outer program", nodex)
emit("JACKPOTS >= $50 outer program", jack)

miss = sum(1 for r in late if not r["found"])
same = sum(1 for r in late if r["same_as_old"])
print(f"\npredecessor found {len(late)-miss}/{len(late)}  matches old trigger label {same}/{len(late)}")
print(f"pool in current 171: {sum(1 for r in late if r['in_universe'])}")

print("\nJACKPOT ROWS")
for r in sorted(jack, key=lambda x: -x["profit"]):
    pools = (r.get("dlmm_pools") or [])[:2] + (r.get("pump_pools") or [])[:2]
    print(f"  ${r['profit']:.1f}  {r['shape']}  dist={r['dist']}  same={r['same_as_old']}")
    print(f"    outer={r['full']}")
    print(f"    inner={[x for x in (r.get('inner') or []) if x not in ('Token Program','Token-2022','Associated Token Program')][:8]}")
    print(f"    pools={pools}")

# $385 detail
print("\nLARGEST DETAIL")
top = max(rows, key=lambda r: r["profit"])
tx = t.load_tx(top["pred_sig"]) if top.get("pred_sig") else None
info = t.analyze_tx(tx, names) if tx else {}
print(json.dumps({
    "profit": top["profit"],
    "frame_why": top["frame_why"],
    "shape": top["shape"],
    "outer_ids": info.get("outer_ids"),
    "inner": info.get("inner"),
    "dlmm_pools": info.get("dlmm_pools"),
    "pump_pools": info.get("pump_pools"),
    "top_deltas": info.get("top_deltas"),
    "dist": top["dist"],
    "same_as_old": top["same_as_old"],
    "pred_sig": top.get("pred_sig"),
}, indent=2)[:4000])
