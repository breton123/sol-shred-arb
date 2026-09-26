#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from reduce_buy013 import analyze_buy, collect, fee, pred_buy_quote
from replay import _dir_amt


def main() -> None:
    root = Path("/data/bsc/captures/soak_fastsoak_20260925/state008")
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    pools = {int(p["idx"]): p for p in u.get("pools") or []}
    buys, _ = collect(root / "mismatch", pools)
    rows = []
    for b in buys:
        r = analyze_buy(b, pools)
        if not r:
            continue
        p = pools.get(int(r["idx"] or -1), {})
        r["quote_mint"] = p.get("my") or p.get("mx") or "?"
        r["base_mint"] = p.get("mx")
        rows.append((b, r))

    for idx in (216, 399, 212):
        sub = [r for _, r in rows if r["idx"] == idx]
        if not sub:
            continue
        print("POOL", idx, "n", len(sub), "mint", sub[0]["quote_mint"][:12], "cr", Counter(x["creator_bps_hit"] for x in sub))
        x = sub[0]
        print("  sample ain", x["ain"], "pred", x["pred_dq"], "pub", x["pub_dq"], "res", x["residual"], "bps", x["residual_bps"], "fees", x["fees"])

    # fees on GROSS ain
    gross_hit = 0
    for b, r in rows:
        sb = b["s_before"]
        ain = r["ain"]
        pr = fee(ain, int(sb.get("protocol_fee_bps") or 0))
        cr = fee(ain, int(sb.get("creator_fee_bps") or 0))
        if ain - pr - cr == r["pub_dq"]:
            gross_hit += 1
    print("gross_ain_pr_cr", gross_hit)

    # mint x invert success
    mint_ok = defaultdict(lambda: Counter())
    for _, r in rows:
        mint_ok[r["quote_mint"][:16]]["hit" if r["creator_bps_hit"] is not None else "none"] += 1
    print("mint", dict((k, dict(v)) for k, v in mint_ok.items()))

    # try fee(ain, 100) etc common
    extra_hits = Counter()
    for _, r in rows:
        ain, res = r["ain"], r["residual"]
        for bps in (25, 30, 50, 80, 90, 95, 100, 200, 250, 300):
            if fee(ain, bps) == res:
                extra_hits[f"fee(ain,{bps})"] += 1
    print("extra_ain", dict(extra_hits))


if __name__ == "__main__":
    main()
