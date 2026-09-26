#!/usr/bin/env python3
"""Re-simulate the last signed dir1 tx and dump Pump CPI data + remaining 26."""
import base64
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
OUR = "38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K"
NAMES26 = [
    "pool", "user", "global", "base_mint", "quote_mint",
    "user_base", "user_quote", "pool_base", "pool_quote",
    "proto_fee", "proto_fee_ata", "base_tok", "quote_tok", "sys", "ata",
    "event", "pump", "creator_ata", "creator_auth",
    "gvol", "uvol", "fee_cfg", "fee_prog", "pool_v2", "fee_rec", "fee_ata",
]


def main():
    live.load_dotenv()
    tx = Path("/home/louis/arb-cap/exec_live002b/signed.tx").read_bytes()
    raw = base64.b64encode(tx).decode()
    res = d.rpc("simulateTransaction", [
        raw,
        {
            "encoding": "base64",
            "replaceRecentBlockhash": True,
            "sigVerify": False,
            "innerInstructions": True,
        },
    ])
    val = res.get("value") or res
    print("err", val.get("err"), "cu", val.get("unitsConsumed"))
    for g in val.get("innerInstructions") or []:
        print(f"inner idx={g.get('index')} n={len(g.get('instructions') or [])}")
        for j, ix in enumerate(g.get("instructions") or []):
            pid = ix.get("programId")
            data = ix.get("data")
            rawb = d._b58_any(data) if isinstance(data, str) else bytes(data or [])
            accs = ix.get("accounts") or []
            print(f"  [{j}] {pid} dlen={len(rawb)} hex={rawb.hex()}")
            if len(rawb) >= 24:
                print("      u64s", list(struct.unpack_from("<" + "Q" * ((len(rawb) - 8) // 8), rawb, 8)),
                      "tail", rawb[8 + 8 * ((len(rawb) - 8) // 8):].hex())
            if pid == PUMP or (isinstance(pid, str) and pid.startswith("pAMM")):
                print("      nacc", len(accs))
                fetched = d.get_multiple(accs)
                for i, a in enumerate(accs):
                    info = fetched[i]
                    amt = None
                    if info and len(info.get("data") or b"") >= 72:
                        amt = struct.unpack_from("<Q", info["data"], 64)[0]
                    lab = NAMES26[i] if i < len(NAMES26) else str(i)
                    print(f"      [{i:02d}] {lab:16s} {a} owner={(info or {}).get('owner')} amt={amt}")


if __name__ == "__main__":
    raise SystemExit(main() or 0)
