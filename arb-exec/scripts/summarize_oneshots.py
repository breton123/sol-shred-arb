#!/usr/bin/env python3
"""Wallet + RESULT reconstruction for ONESHOT losses. No send."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
sys.path.insert(0, "/home/louis/arb-cap/paper004")
import live001 as live
import paper004 as p4

W = "HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"
OUR_EXEC = "38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K"
RESULT = Path("/home/louis/arb-cap/oneshot/RESULT.json")
AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")


def n_status(sig_hex: str) -> dict:
    if not sig_hex:
        return {}
    sig = p4.b58encode(bytes.fromhex(sig_hex))
    st = p4.rpc("getSignatureStatuses", [[sig], {"searchTransactionHistory": True}])
    ent = ((st or {}).get("value") or [None])[0]
    return {"n_sig": sig, "n_status": ent, "n_landed": bool(ent and ent.get("err") is None)}


def main():
    live.load_dotenv()
    res = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    fire = res.get("fire") or {}
    opp = res.get("opp") or {}
    print("LAST_RESULT", json.dumps({
        "why": res.get("why"),
        "dir": fire.get("direction"),
        "send": fire.get("send_lamports"),
        "est_gp": fire.get("est_gp"),
        "sig": fire.get("sig"),
        "dlmm": fire.get("dlmm"),
        "pump": fire.get("pump"),
        "alt": fire.get("alt"),
        "swqos_ns_line": (fire.get("swqos_out") or "")[:80],
        "timing": fire.get("timing"),
        "n": opp.get("n"),
        "arb": opp.get("arb"),
        "pool": opp.get("pool"),
        "sig_hex": opp.get("sig_hex"),
        "timing_paper": opp.get("timing"),
        "auth_slot": opp.get("auth_slot"),
        "N": n_status(opp.get("sig_hex") or ""),
    }, indent=2))

    sigs = p4.rpc("getSignaturesForAddress", [W, {"limit": 15}], pause=0.25) or []
    print("WALLET_TXS")
    for ent in sigs:
        sig = ent.get("signature")
        tx = None
        try:
            tx = p4.fetch_tx(sig)
        except Exception:
            pass
        pids = p4.ix_pids(tx) if tx else set()
        if OUR_EXEC not in pids and sig != fire.get("sig"):
            continue
        print(json.dumps({
            "sig": sig,
            "slot": (tx or {}).get("slot") or ent.get("slot"),
            "bt": (tx or {}).get("blockTime") or ent.get("blockTime"),
            "err": ((tx or {}).get("meta") or {}).get("err") or ent.get("err"),
            "fee": ((tx or {}).get("meta") or {}).get("fee"),
        }))


if __name__ == "__main__":
    raise SystemExit(main() or 0)
