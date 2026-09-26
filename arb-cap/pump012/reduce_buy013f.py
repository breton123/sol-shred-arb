#!/usr/bin/env python3
"""Apply LIVE Pool.creator_fee_bps to the 1003. Does current on-chain field explain soak residuals?"""
from __future__ import annotations

import json
import os
import base64
import urllib.request
from collections import Counter
from pathlib import Path

from reduce_buy013 import collect, fee
from replay import _dir_amt


def fetch_creator(pks: list[str]) -> dict[str, dict]:
    url = os.environ["HELIUS_RPC_URL"]
    out = {}
    for i in range(0, len(pks), 80):
        chunk = pks[i:i + 80]
        body = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "getMultipleAccounts",
            "params": [chunk, {"encoding": "base64"}],
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        vals = json.loads(urllib.request.urlopen(req, timeout=30).read())["result"]["value"]
        for pk, acc in zip(chunk, vals):
            if not acc:
                continue
            raw = base64.b64decode(acc["data"][0])
            out[pk] = {
                "creator_bps": int.from_bytes(raw[261:269], "little") if len(raw) >= 269 else None,
                "holder": raw[270] if len(raw) > 270 else None,
                "cashback": raw[244] if len(raw) > 244 else None,
                "virt": int.from_bytes(raw[245:261], "little", signed=True) if len(raw) >= 261 else None,
            }
    return out


def expect_dq(ain, lp_b, pr_b, cr_b):
    tot = lp_b + pr_b + cr_b
    eff = ain * 10000 // (10000 + tot)
    return ain - fee(eff, pr_b) - fee(eff, cr_b)


def main() -> None:
    root = Path("/data/bsc/captures/soak_fastsoak_20260925/state008")
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    meta = {int(p["idx"]): p for p in u.get("pools") or []}
    buys, _ = collect(root / "mismatch", meta)
    pks = sorted({meta[int(b["idx"])]["pubkey"] for b in buys if b.get("idx") in meta})
    info = fetch_creator(pks)
    hit = Counter()
    for b in buys:
        idx = int(b["idx"])
        pk = meta[idx]["pubkey"]
        inf = info.get(pk) or {}
        cr = inf.get("creator_bps")
        _, ain = _dir_amt(b)
        sb, pu = b["s_before"], b["published_s"]
        pub = int(pu["reserve_quote"]) - int(sb["reserve_quote"])
        lp_b, pr_b = int(sb["lp_fee_bps"]), int(sb["protocol_fee_bps"])
        if cr is None:
            hit["no_acc"] += 1
            continue
        if expect_dq(ain, lp_b, pr_b, cr) == pub:
            hit[f"pool_cr={cr}"] += 1
            hit["pool_cr_any"] += 1
        elif expect_dq(ain, lp_b, pr_b, 0) == pub:
            hit["force_cr0"] += 1
        elif ain - fee(ain * 10000 // (10000 + lp_b + pr_b + 5), pr_b) == pub:
            hit["debit_proto_only_price_g5"] += 1
        else:
            hit["miss"] += 1
            hit[f"miss_cr{cr}_h{inf.get('holder')}"] += 1
    print(json.dumps({"n": len(buys), "pools": len(pks), "hits": dict(hit)}, indent=2))


if __name__ == "__main__":
    main()
