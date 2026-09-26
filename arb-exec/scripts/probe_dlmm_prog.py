#!/usr/bin/env python3
"""Find a recent successful DLMM swap2 anywhere, dump accounts + data."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

PAIR = "DAErPzgiYQDhDwpMRgdvikXaZmnmznc3du3jy9i1AABk"


def main() -> int:
    live.load_dotenv()
    sigs = d.rpc("getSignaturesForAddress", [d.DLMM, {"limit": 15}])
    n = 0
    for s in sigs:
        tx = d.rpc(
            "getTransaction",
            [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}],
        )
        sw = d.decode_swaps(tx) if tx else []
        if not sw:
            continue
        n += 1
        x = sw[0]
        print(f"sig={s['signature'][:16]}.. pair={x['pair'][:8]} nacc={len(x['accounts'])} "
              f"in={x['amount_in']} min={x['min_out']} our={x['pair']==PAIR}")
        for i, a in enumerate(x["accounts"]):
            print(f"  [{i:02d}] {a}")
        if n >= 2:
            break
    if n == 0:
        print("no swap2 in last 15 DLMM program sigs")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
