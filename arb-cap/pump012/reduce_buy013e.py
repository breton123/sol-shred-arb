#!/usr/bin/env python3
"""Score: one creator_bps per pool (mode) + kernel buy vault identity."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from reduce_buy013 import analyze_buy, collect, fee, pred_buy_quote
from replay import _dir_amt
from pump_apply import apply_swap, invert_virtual


def pub_with_creator(ain: int, lp_b: int, pr_b: int, cr_b: int) -> int:
    tot = lp_b + pr_b + cr_b
    if tot >= 10000:
        return -1
    eff = ain * 10000 // (10000 + tot)
    return ain - fee(eff, pr_b) - fee(eff, cr_b)


def main() -> None:
    root = Path("/data/bsc/captures/soak_fastsoak_20260925/state008")
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    pools = {int(p["idx"]): p for p in u.get("pools") or []}
    buys, cleans = collect(root / "mismatch", pools)
    rows = []
    for b in buys:
        r = analyze_buy(b, pools)
        if r:
            rows.append((b, r))

    votes = defaultdict(Counter)
    for b, r in rows:
        if r["creator_bps_hit"] is not None:
            votes[r["idx"]][r["creator_bps_hit"]] += 1
    mode = {i: c.most_common(1)[0][0] for i, c in votes.items()}

    hit = miss = no_mode = 0
    miss_idx = Counter()
    for b, r in rows:
        cr = mode.get(r["idx"])
        if cr is None:
            no_mode += 1
            continue
        sb = b["s_before"]
        got = pub_with_creator(r["ain"], int(sb["lp_fee_bps"]), int(sb["protocol_fee_bps"]), cr)
        if got == r["pub_dq"]:
            hit += 1
        else:
            miss += 1
            miss_idx[r["idx"]] += 1

    # sell regression unchanged
    sell_ok = 0
    for b in cleans:
        d, ain = _dir_amt(b)
        if d != 1:
            continue
        v = invert_virtual(b["s_before"], ain, 1, b["published_s"])
        g = apply_swap({**b["s_before"], "virtual_quote": v}, ain, 1) if v is not None else None
        pu = b["published_s"]
        if g and g["reserve_base"] == int(pu["reserve_base"]) and g["reserve_quote"] == int(pu["reserve_quote"]):
            sell_ok += 1

    print(json.dumps({
        "n": len(rows),
        "mode_pools": len(mode),
        "hit_mode_creator": hit,
        "miss_mode_creator": miss,
        "no_mode": no_mode,
        "miss_top_idx": dict(miss_idx.most_common(8)),
        "sell_ok": sell_ok,
        "pct": round(100 * hit / len(rows), 1) if rows else 0,
    }, indent=2))


if __name__ == "__main__":
    main()
