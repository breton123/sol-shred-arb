"""PUMP-AUTH-016 overlay from geyser-parsed ixs. No C kernel change."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# shyft -> arb-state -> repo  (local). On box: shyft -> arb-state -> /home/louis
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "arb-cap" / "pump012"))
sys.path.insert(0, str(Path("/home/louis/arb-cap/pump012")))

import txexpect as txe  # noqa: E402
from pump_overlay import apply_sequence  # noqa: E402

KIND = {
    "pump_sell": "sell",
    "pump_buy_exact_quote": "buy_exact_quote_in",
    "pump_buy_exact_out": "buy_exact_out",
}


def cpis_from_parsed(ixs: list[dict], pool: str) -> list[dict]:
    out = []
    for ix in ixs or []:
        prog = ix.get("program") or ""
        if prog != txe.PUMP:
            continue
        accs = list(ix.get("accounts") or [])
        if not accs or accs[0] != pool:
            continue
        data = ix.get("data") or b""
        if isinstance(data, str):
            out.append({"kind": "unknown", "pool": pool})
            continue
        v = txe.classify_ix(prog, data)
        kind = KIND.get(v or "")
        if kind is None:
            out.append({
                "kind": "unknown", "pool": pool,
                "outer_ix": ix.get("outer_ix"),
                "inner_ordinal": ix.get("inner_ordinal"),
            })
            continue
        amt = int.from_bytes(data[8:16], "little") if len(data) >= 16 else None
        mx = int.from_bytes(data[16:24], "little") if len(data) >= 24 else None
        out.append({
            "kind": kind,
            "amount": amt,
            "max_quote": mx if kind == "buy_exact_out" else None,
            "pool": pool,
            "direction": 1 if kind == "sell" else 0,
            "src_ata": accs[5] if kind == "sell" and len(accs) > 5 else (accs[6] if len(accs) > 6 else None),
            "dst_ata": accs[7] if kind == "sell" and len(accs) > 7 else (accs[8] if len(accs) > 8 else None),
            "outer_ix": ix.get("outer_ix"),
            "inner_ordinal": ix.get("inner_ordinal"),
        })
    return out


def apply_parsed(last_s: dict, cpis: list[dict]):
    return apply_sequence(last_s, cpis)
