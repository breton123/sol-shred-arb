#!/usr/bin/env python3
"""Read-only ONESHOT#5 N vs ours. No send."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
sys.path.insert(0, "/home/louis/arb-exec/scripts")
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

live.load_dotenv()

OUR = "5FdNDoD9aqSJcxFQk9d2quNq893X12vrsSsoxxVBjhWmrnTAHRFniwDhVaMnK8PbcG4pr98EwRK2mgXggHn43Yss"
N = "3699XKMRSEkz3uxqVaUBqGdab6WK6LUM4UMexwVP17NiVjy3MQgiTeBYfQvFcZ6yGdcfiQ9SPT3oUECWAUjNNzTF"
RES = Path("/home/louis/arb-cap/oneshot/RESULT.json")


def one(label: str, sig: str) -> dict:
    tx = d.rpc(
        "getTransaction",
        [sig, {"encoding": "json", "maxSupportedTransactionVersion": 0, "commitment": "confirmed"}],
    )
    out = {"label": label, "sig": sig, "have": bool(tx)}
    if not tx:
        return out
    meta = tx.get("meta") or {}
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = msg.get("accountKeys") or []
    ixs = msg.get("instructions") or []
    logs = meta.get("logMessages") or []
    out.update(
        {
            "slot": tx.get("slot"),
            "fee": meta.get("fee"),
            "err": meta.get("err"),
            "n_ix": len(ixs),
            "ix": [],
            "logs": logs,
        }
    )
    for i, ix in enumerate(ixs):
        pid = ix.get("programIdIndex")
        pk = keys[pid] if isinstance(pid, int) and pid < len(keys) else pid
        out["ix"].append({"i": i, "prog": pk, "data_len": len(ix.get("data") or "")})
    return out


def main() -> None:
    res = json.loads(RES.read_text(encoding="utf-8"))
    fire = res.get("fire") or {}
    rec = res.get("opp") or {}
    td = fire["timing"]["T_decision_mono_ns"]
    ts = fire["timing"]["T_signed_mono_ns"]
    tw = fire["timing"]["T_SWQOS_return_mono_ns"]
    ntx = one("N", N)
    otx = one("OURS", OUR)
    print(
        json.dumps(
            {
                "why": res.get("why"),
                "n_outcome": (res.get("trigger") or {}).get("n_outcome"),
                "slot_n": ntx.get("slot"),
                "slot_ours": otx.get("slot"),
                "slot_delta": (otx.get("slot") or 0) - (ntx.get("slot") or 0),
                "resolve_pair_ms": (ts - td) / 1e6,
                "swqos_mono_ms": (tw - ts) / 1e6,
                "send_wall_ms": fire.get("send_wall_ms"),
                "paper_decision_ns": (rec.get("timing") or {}).get("decision_ns"),
                "paper_signed_ns": (rec.get("timing") or {}).get("signed_ready_ns"),
                "frame_delay_ns": (rec.get("frame") or {}).get("delay_ns"),
                "auth_slot": rec.get("auth_slot"),
                "state_ver": rec.get("state_version_before"),
                "shred_slot": (rec.get("shred") or {}).get("slot"),
                "send_quote": rec.get("send_quote"),
                "arb": rec.get("arb"),
                "n_ix_n": rec.get("n"),
                "n_tx": {
                    "fee": ntx.get("fee"),
                    "err": ntx.get("err"),
                    "ix": ntx.get("ix"),
                    "logs_tail": (ntx.get("logs") or [])[-12:],
                },
                "ours_tx": {
                    "fee": otx.get("fee"),
                    "err": otx.get("err"),
                    "ix": otx.get("ix"),
                    "logs": otx.get("logs"),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
