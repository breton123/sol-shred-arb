#!/usr/bin/env python3
"""Test vault debit identities on the 1003: who leaves the quote vault."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from reduce_buy013 import collect, fee, pred_buy_quote
from replay import _dir_amt, replay_one
from pump_apply import apply_swap, invert_virtual


def main() -> None:
    root = Path("/data/bsc/captures/soak_fastsoak_20260925/state008")
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    pools = {int(p["idx"]): p for p in u.get("pools") or []}
    buys, cleans = collect(root / "mismatch", pools)

    ids = Counter()
    for b in buys:
        sb, pu = b["s_before"], b["published_s"]
        _, ain = _dir_amt(b)
        pred, f = pred_buy_quote(sb, ain)
        pub = int(pu["reserve_quote"]) - int(sb["reserve_quote"])
        ain_pr = ain - f["proto"]
        ain_cr = ain - f["creator"]
        ain_prcr = ain - f["proto"] - f["creator"]
        ain_all = ain - f["lp"] - f["proto"] - f["creator"]
        if pub == pred:
            ids["pred_kernel"] += 1
        if pub == ain_pr:
            ids["ain-proto"] += 1
        if pub == ain_cr:
            ids["ain-creator"] += 1
        if pub == ain_prcr:
            ids["ain-proto-creator"] += 1
        if pub == ain_all:
            ids["ain-all"] += 1
        if pub == ain:
            ids["ain"] += 1
        if pub == f["effective"]:
            ids["effective"] += 1

    # apply buy with creator_bps=0 for vault subtract only? 
    # regression: sells with kernel unchanged
    sell_ok = 0
    for b in cleans:
        d, ain = _dir_amt(b)
        if d != 1:
            continue
        v = invert_virtual(b["s_before"], ain, 1, b["published_s"])
        g = apply_swap({**b["s_before"], "virtual_quote": v}, ain, 1) if v is not None else None
        pu = b["published_s"]
        if g and g["reserve_quote"] == int(pu["reserve_quote"]) and g["reserve_base"] == int(pu["reserve_base"]):
            sell_ok += 1

    print("identities", dict(ids))
    print("n", len(buys), "sell_ok", sell_ok)


if __name__ == "__main__":
    main()
