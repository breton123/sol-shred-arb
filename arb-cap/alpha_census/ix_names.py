#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

OUT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\alpha_census")
for name in ("dlmm_idl.json", "pump_idl.json"):
    doc = json.loads((OUT / name).read_text(encoding="utf-8"))
    ixs = doc.get("instructions") or []
    print(name, len(ixs))
    print(", ".join(i["name"] for i in ixs))
    print("---")

rows = [json.loads(l) for l in (OUT / "joined2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
c = Counter()
for r in rows:
    if r["program"] != "dlmm" or r["trigger_class"] == "no_invoke":
        continue
    for ix in r["instructions"]:
        c[ix] += 1
print("DLMM_IX_IN_INVOKED_TXS")
for k, v in c.most_common():
    print(f"{v:4} {k}")
print("liquidity_rows", sum(1 for r in rows if r["trigger_class"] == "liquidity"))
print("window_check sample slots", min(r["slot"] for r in rows), max(r["slot"] for r in rows))
