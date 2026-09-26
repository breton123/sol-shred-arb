#!/usr/bin/env python3
"""Dump live Pump sell account vector. No send."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PAIR = "BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs"


def ix_accounts(ix, keys):
    out = []
    for a in ix.get("accounts") or []:
        out.append(keys[a] if isinstance(a, int) else a)
    return out


def ix_program(ix, keys):
    pid = ix.get("programId")
    if pid is not None:
        return pid
    idx = ix.get("programIdIndex")
    if idx is not None and idx < len(keys):
        return keys[idx]
    return None


def main() -> int:
    live.load_dotenv()
    sigs = d.rpc("getSignaturesForAddress", [PAIR, {"limit": 16}])
    for s in sigs:
        tx = d.rpc("getTransaction", [
            s["signature"],
            {"encoding": "json", "maxSupportedTransactionVersion": 1},
        ])
        if not tx or (tx.get("meta") or {}).get("err"):
            continue
        keys = d.tx_keys(tx)
        ixs = list(tx["transaction"]["message"].get("instructions") or [])
        for g in (tx.get("meta") or {}).get("innerInstructions") or []:
            ixs.extend(g.get("instructions") or [])
        for ix in ixs:
            if ix_program(ix, keys) != PUMP:
                continue
            accs = ix_accounts(ix, keys)
            raw = ix.get("data")
            data = d._b58_any(raw) if isinstance(raw, str) else bytes(raw or [])
            if not accs or accs[0] != PAIR or len(data) < 8:
                continue
            disc = data[:8].hex()
            print(f"sig={s['signature'][:12]} n={len(accs)} disc={disc}")
            for i, a in enumerate(accs):
                print(f"  {i:02} {a}")
            return 0
    print("no live sell")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
