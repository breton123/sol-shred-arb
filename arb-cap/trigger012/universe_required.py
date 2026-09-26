#!/usr/bin/env python3
"""Pools that successful-market predecessors actually touched.

Rule: if a causal predecessor invoked DLMM or Pump, that pool belongs
in the universe. Not 'was it one of today's 171'.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
HERE = Path(__file__).resolve().parent
FUNNEL = HERE / "funnel012.jsonl"
UNIV = ROOT / "arb-cap" / "regress" / "liveuniv_now.json"
OUT = HERE / "required_pools.json"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    watch = {p["pubkey"] for p in json.loads(UNIV.read_text(encoding="utf-8")).get("pools") or []}
    rows = [json.loads(l) for l in FUNNEL.read_text(encoding="utf-8").splitlines() if l.strip()]
    SWAP = {
        "33e685a4017f83ad",  # pump sell
        "c62e1552b4d9e870",  # pump buy_eq
        "66063d1201daebea",  # pump buy
        "414b3f4ceb5b5b88",  # dlmm swap2
        "f8c69e91e17587c8",  # dlmm swap
    }
    # PDAs that show up as acc[0] on fee/event inner ixs — not pools.
    NOT_POOL = {
        "GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR",
        "D1ZN9Wj1fRSUQfCjhvnu1hqDMT7hzjzBBpi12nVniYD6",
        "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ",
    }
    freq = Counter()
    usd = Counter()
    proto = {}
    for r in rows:
        for op in r.get("ops") or []:
            p = op.get("pool")
            if not p or p in NOT_POOL:
                continue
            if op.get("disc") not in SWAP:
                continue
            freq[p] += 1
            usd[p] += r.get("usd") or 0
            proto[p] = op.get("proto")
    required = []
    for p, n in freq.most_common():
        required.append({
            "pool": p,
            "proto": proto.get(p),
            "pred_n": n,
            "usd": usd[p],
            "in_univ": p in watch,
        })
    missing = [x for x in required if not x["in_univ"]]
    doc = {
        "current_univ": len(watch),
        "required": len(required),
        "missing": len(missing),
        "missing_usd": sum(x["usd"] for x in missing),
        "in_univ_usd": sum(x["usd"] for x in required if x["in_univ"]),
        "over_256": len(required) > 256,
        "over_171": len(required) > len(watch),
        "pools": required,
    }
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"current univ {len(watch)}")
    print(f"required unique DLMM/Pump pools {len(required)}  missing {len(missing)}  ${doc['missing_usd']:.1f}")
    print(f"over_256={doc['over_256']}")
    print("top missing:")
    for x in missing[:15]:
        print(f"  {x['usd']:8.1f}  n={x['pred_n']:4}  {x['proto']}  {x['pool']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
