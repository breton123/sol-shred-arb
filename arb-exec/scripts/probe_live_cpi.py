#!/usr/bin/env python3
"""EXEC-LIVE-001 probe. Prints pubkeys, balances, live CPI layouts. Never prints secrets."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PAIR_DLMM = "DAErPzgiYQDhDwpMRgdvikXaZmnmznc3du3jy9i1AABk"
PAIR_PUMP = "BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs"


def b58_any(s: str) -> bytes:
    alph = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in s:
        n = n * 58 + alph.index(c)
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    h = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + h


def pubkey_from_env() -> str | None:
    pk = os.environ.get("PUBLIC_KEY")
    if pk:
        return pk.strip()
    raw = os.environ.get("PRIVATE_KEY", "").strip()
    if not raw:
        return None
    secret = b58_any(raw)
    if len(secret) == 64:
        return d._pk(secret[32:])
    if len(secret) == 32:
        from nacl.signing import SigningKey

        return d._pk(bytes(SigningKey(secret).verify_key))
    print(f"PRIVATE_KEY decoded length={len(secret)} (expected 32 or 64)", file=sys.stderr)
    return None


def ix_accounts(ix: dict, keys: list[str]) -> list[str]:
    out = []
    for a in ix.get("accounts") or []:
        out.append(keys[a] if isinstance(a, int) else a)
    return out


def ix_data(ix: dict) -> bytes:
    raw = ix.get("data")
    if isinstance(raw, str):
        return d._b58_any(raw) if hasattr(d, "_b58_any") else b58_any(raw)
    return bytes(raw or [])


def ix_program(ix: dict, keys: list[str]) -> str | None:
    pid = ix.get("programId")
    if pid is not None:
        return pid
    idx = ix.get("programIdIndex")
    if idx is not None and idx < len(keys):
        return keys[idx]
    return None


def dump_ix(label: str, ix: dict, keys: list[str]) -> None:
    data = ix_data(ix)
    accs = ix_accounts(ix, keys)
    print(f"  {label} data_len={len(data)} disc={data[:8].hex()} nacc={len(accs)}")
    if len(data) >= 24:
        a, b = struct.unpack_from("<QQ", data, 8)
        print(f"    u64[0]={a} u64[1]={b} tail={data[24:].hex()}")
    for i, a in enumerate(accs):
        print(f"    [{i:02d}] {a}")


def main() -> int:
    live.load_dotenv()
    names = sorted(k for k in os.environ if k in (
        "RPC_URL", "HELIUS_RPC_URL", "HELIUS_API_KEY", "PRIVATE_KEY", "PUBLIC_KEY"
    ))
    print("env keys present:", " ".join(names))
    pub = pubkey_from_env()
    print("wallet:", pub or "(none)")
    if pub:
        bal = d.rpc("getBalance", [pub])
        lamports = bal["value"] if isinstance(bal, dict) else bal
        print(f"balance_sol={lamports / 1e9:.6f}  lamports={lamports}")

    for pair, tag in ((PAIR_DLMM, "dlmm"), (PAIR_PUMP, "pump")):
        sigs = d.rpc("getSignaturesForAddress", [pair, {"limit": 8}])
        print(f"\n{tag} {pair[:8]}.. recent={len(sigs)}")
        for s in sigs[:4]:
            tx = d.rpc(
                "getTransaction",
                [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}],
            )
            if not tx:
                continue
            keys = d.tx_keys(tx)
            err = (tx.get("meta") or {}).get("err")
            cu = (tx.get("meta") or {}).get("computeUnitsConsumed")
            print(f"  sig={s['signature'][:12]}.. slot={s.get('slot')} err={err} cu={cu}")
            msg_ixs = list((tx["transaction"]["message"].get("instructions") or []))
            inner = []
            for g in (tx.get("meta") or {}).get("innerInstructions") or []:
                inner.extend(g.get("instructions") or [])
            for ix in msg_ixs + inner:
                pid = ix_program(ix, keys)
                if pid == DLMM:
                    dump_ix("DLMM", ix, keys)
                elif pid == PUMP:
                    dump_ix("PUMP", ix, keys)

    print("\n--- live pair accounts ---")
    sn = d.snapshot_pool(PAIR_DLMM, [PAIR_DLMM], None)
    if sn and sn.get("lb"):
        lb = sn["lb"]
        print("dlmm active_id", lb["active_id"], "bins", len(sn["bins"]))
        print("  mint_x", d._pk(lb["token_x"]))
        print("  mint_y", d._pk(lb["token_y"]))
        print("  vault_x", d._pk(lb["vault_x"]))
        print("  vault_y", d._pk(lb["vault_y"]))
        for idx in d.array_indexes(lb["active_id"]):
            print("  bin", idx, d.bin_array_pda(PAIR_DLMM, idx))
        oracle = d.find_pda([b"oracle", d.b58decode(PAIR_DLMM)], d.b58decode(DLMM))
        bitmap = d.find_pda([b"bitmap", d.b58decode(PAIR_DLMM)], d.b58decode(DLMM))
        ev = d.find_pda([b"__event_authority"], d.b58decode(DLMM))
        print("  oracle_pda", d._pk(oracle))
        print("  bitmap_pda", d._pk(bitmap))
        print("  event_auth", d._pk(ev))
        accs = d.get_multiple([d._pk(oracle), d._pk(bitmap)])
        print("  oracle exists", bool(accs[0]), "bitmap exists", bool(accs[1]))
        mints = d.get_multiple([d._pk(lb["token_x"]), d._pk(lb["token_y"])])
        for name, a in zip(("x", "y"), mints):
            if a:
                print(f"  mint_{name} owner={a['owner']} dlen={len(a['data'])}")

    pacc = d.get_multiple([PAIR_PUMP])[0]
    if pacc:
        p = live.parse_pump_pool(pacc["data"])
        print("pump exists dlen", len(pacc["data"]))
        if p:
            print("  base", d._pk(p["base"]))
            print("  quote", d._pk(p["quote"]))
            print("  vault_b", d._pk(p["vault_base"]))
            print("  vault_q", d._pk(p["vault_quote"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
