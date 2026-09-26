#!/usr/bin/env python3
"""Dump one live DAErPzgi tx: every ix program + data length."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

PAIR = "DAErPzgiYQDhDwpMRgdvikXaZmnmznc3du3jy9i1AABk"
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"


def main() -> int:
    live.load_dotenv()
    sigs = d.rpc("getSignaturesForAddress", [PAIR, {"limit": 20}])
    sig = None
    tx = None
    for s in sigs:
        cand = d.rpc(
            "getTransaction",
            [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}],
        )
        if not cand:
            continue
        keys = d.tx_keys(cand)
        found = False
        for g in (cand.get("meta") or {}).get("innerInstructions") or []:
            for ix in g.get("instructions") or []:
                pid = ix.get("programId")
                if pid is None:
                    idx = ix.get("programIdIndex")
                    pid = keys[idx] if idx is not None and idx < len(keys) else None
                if pid == DLMM:
                    found = True
                    break
            if found:
                break
        if found and not (cand.get("meta") or {}).get("err"):
            sig = s["signature"]
            tx = cand
            break
    if tx is None:
        print("no successful DLMM inner in last 20")
        return 1
    print("sig", sig)
    keys = d.tx_keys(tx)
    print("nkeys", len(keys), "err", (tx.get("meta") or {}).get("err"),
          "cu", (tx.get("meta") or {}).get("computeUnitsConsumed"))
    print("log0", ((tx.get("meta") or {}).get("logMessages") or [""])[0][:120])
    ixs = list(tx["transaction"]["message"].get("instructions") or [])
    print("top-level", len(ixs))
    for i, ix in enumerate(ixs):
        pid = ix.get("programId")
        if pid is None:
            idx = ix.get("programIdIndex")
            pid = keys[idx] if idx is not None else None
        data = ix.get("data")
        dlen = len(d._b58_any(data)) if isinstance(data, str) else 0
        nacc = len(ix.get("accounts") or [])
        print(f"  top[{i}] {pid} dlen={dlen} nacc={nacc}")
    for g in (tx.get("meta") or {}).get("innerInstructions") or []:
        print("inner idx", g.get("index"), "n", len(g.get("instructions") or []))
        for j, ix in enumerate(g.get("instructions") or []):
            pid = ix.get("programId")
            if pid is None:
                idx = ix.get("programIdIndex")
                pid = keys[idx] if idx is not None else "?"
            data = ix.get("data")
            raw = d._b58_any(data) if isinstance(data, str) else b""
            nacc = len(ix.get("accounts") or [])
            mark = " <<" if pid == DLMM else ""
            print(f"    [{j}] {pid} dlen={len(raw)} disc={raw[:8].hex()} nacc={nacc}{mark}")
            if pid == DLMM:
                accs = []
                for a in ix.get("accounts") or []:
                    accs.append(keys[a] if isinstance(a, int) else a)
                for k, a in enumerate(accs):
                    print(f"       [{k:02d}] {a}")
                print("       tail", raw[8:].hex())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
