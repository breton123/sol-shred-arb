#!/usr/bin/env python3
"""Per-pool uniqueness of inverted creator_bps + mint split + None leftovers."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from reduce_buy013 import analyze_buy, collect, load_pools, pred_buy_quote
from replay import _dir_amt


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/data/bsc/captures/soak_fastsoak_20260925/state008")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent
    pools = {}
    univ = Path("/home/louis/captures/paper_orbit/liveuniv.json")
    if univ.exists():
        u = json.loads(univ.read_text())
        for p in u.get("pools") or []:
            pools[int(p["idx"])] = p
    buys, cleans = collect(root / "mismatch", pools)
    rows = [analyze_buy(b, pools) for b in buys]
    rows = [r for r in rows if r]

    by_idx = defaultdict(set)
    mint_cr = defaultdict(Counter)
    none_bps = Counter()
    none_sign = Counter()
    none_idx = Counter()
    for r in rows:
        by_idx[r["idx"]].add(r["creator_bps_hit"])
        mint = r["quote_mint"]
        if mint == "?" and r["idx"] in pools:
            p = pools[r["idx"]]
            mint = p.get("my") or p.get("mx") or "?"
            r["quote_mint"] = mint
        mint_cr[mint[:16]][r["creator_bps_hit"]] += 1
        if r["creator_bps_hit"] is None:
            none_bps[r["residual_bps"]] += 1
            none_sign["neg" if r["residual"] < 0 else "pos"] += 1
            none_idx[r["idx"]] += 1

    unique = mixed = none_pool = 0
    mixed_ex = []
    for idx, s in by_idx.items():
        if None in s and len(s) == 1:
            none_pool += 1
        elif None not in s and len(s) == 1:
            unique += 1
        else:
            mixed += 1
            if len(mixed_ex) < 8:
                mixed_ex.append({"idx": idx, "hits": list(s)})

    # mint wsol vs other
    wsol = "So11111111111111111111111111111111111111112"
    mint_n = Counter(r["quote_mint"] for r in rows)

    doc = {
        "n": len(rows),
        "pools": len(by_idx),
        "pools_one_creator_bps": unique,
        "pools_mixed_or_partial_none": mixed,
        "pools_all_none": none_pool,
        "mixed_examples": mixed_ex,
        "none_n": sum(1 for r in rows if r["creator_bps_hit"] is None),
        "none_sign": dict(none_sign),
        "none_residual_bps": dict(none_bps.most_common(12)),
        "none_top_idx": dict(none_idx.most_common(8)),
        "quote_mint": dict(mint_n.most_common(8)),
        "wsol_n": mint_n.get(wsol, 0),
        "clean_n": len(cleans),
    }
    (out / "PUMP013_POOLS.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps(doc, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
