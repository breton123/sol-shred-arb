#!/usr/bin/env python3
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
BUYQ = bytes.fromhex("c62e1552b4d9e870")
PAIR = "BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs"
TOKENKEG = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
T22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
NAMES26 = [
    "pool", "user", "global", "base_mint", "quote_mint",
    "user_base", "user_quote", "pool_base", "pool_quote",
    "proto_fee", "proto_fee_ata", "base_tok", "quote_tok", "sys", "ata",
    "event", "pump", "creator_ata", "creator_auth",
    "gvol", "uvol", "fee_cfg", "fee_prog", "pool_v2", "fee_rec", "fee_ata",
]


def ix_accounts(ix, keys):
    return [keys[a] if isinstance(a, int) else a for a in (ix.get("accounts") or [])]


def ix_program(ix, keys):
    pid = ix.get("programId")
    if pid is not None:
        return pid
    idx = ix.get("programIdIndex")
    if idx is not None and idx < len(keys):
        return keys[idx]
    return None


def tok_amt(acc):
    if not acc or len(acc.get("data") or b"") < 72:
        return None
    return struct.unpack_from("<Q", acc["data"], 64)[0]


def first_buy():
    sigs = d.rpc("getSignaturesForAddress", [PAIR, {"limit": 30}]) or []
    for ent in sigs:
        if ent.get("err"):
            continue
        tx = d.rpc("getTransaction", [
            ent["signature"],
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
            raw = ix.get("data")
            data = d._b58_any(raw) if isinstance(raw, str) else bytes(raw or [])
            if data[:8] != BUYQ:
                continue
            return ent["signature"], ix_accounts(ix, keys), data
    return None, [], b""


def reconstruct_ours():
    # Mirror exec_live002b loaded/IX_IDX_BUY using report + resolve fields if present.
    rep = json.loads(Path("/home/louis/arb-cap/exec_live002b/report.json").read_text())
    keys_path = Path("/home/louis/arb-cap/exec_live002b/keys.json")
    keys35 = json.loads(keys_path.read_text()) if keys_path.exists() else []
    tx = Path("/home/louis/arb-cap/exec_live002b/signed.tx").read_bytes()
    return rep, keys35, tx


def decode_buy_remaining(tx: bytes):
    # V0 buy: static 11 keys start at offset 7? header: 1 + 64 + 5 + 11*32
    # Safer: use python solders if available; else print raw length.
    return tx


def main():
    live.load_dotenv()
    sig, live_accs, data = first_buy()
    print(f"LIVE sig={sig} n={len(live_accs)} dlen={len(data)} hex={data.hex()}")
    if data and len(data) >= 24:
        print("  spendable", struct.unpack_from("<Q", data, 8)[0],
              "min_base", struct.unpack_from("<Q", data, 16)[0])

    pacc = d.get_multiple([PAIR])[0]
    p = live.parse_pump_pool(pacc["data"]) if pacc else None
    print("POOL parse", {k: (d._pk(v) if isinstance(v, (bytes, bytearray)) else v)
                         for k, v in (p or {}).items()})

    need = list(live_accs)
    vault_b = d._pk(p["vault_base"]) if p else None
    vault_q = d._pk(p["vault_quote"]) if p else None
    for extra in (vault_b, vault_q):
        if extra and extra not in need:
            need.append(extra)
    # our wallet ATAs from report
    rep, keys35, tx = reconstruct_ours()
    print("OUR wallet", rep.get("wallet"), "alt", (rep.get("alt") or "")[:16],
          "tiny", rep.get("tiny_in"), "cu", (rep.get("simulate") or {}).get("cu"))
    print("OUR signed", len(tx), "dir", tx[548] if len(tx) > 557 else None,
          "amt", struct.unpack_from("<Q", tx, 549)[0] if len(tx) > 557 else None,
          "minp", struct.unpack_from("<Q", tx, 557)[0] if len(tx) > 565 else None)

    our_map = {r["name"]: r["pubkey"] for r in (rep.get("accounts") or [])}
    for k in ("user_quote", "user_base", "pump_pool_base", "pump_pool_quote",
              "pump_base_mint", "pump_quote_mint", "pump_global_vol", "pump_user_vol"):
        if k in our_map:
            need.append(our_map[k])
            print(f"  keys35 {k} {our_map[k]}")

    accs = d.get_multiple(need)
    by = {need[i]: accs[i] for i in range(len(need))}

    if live_accs:
        print("LIVE26 vs expected names")
        for i, a in enumerate(live_accs):
            info = by.get(a)
            owner = (info or {}).get("owner")
            amt = tok_amt(info) if info else None
            print(f"  [{i:02d}] {NAMES26[i] if i < 26 else i:16s} {a} owner={owner} amt={amt} dlen={len((info or {}).get('data') or b'')}")

    for label, pk in (("vault_b", vault_b), ("vault_q", vault_q),
                      ("our_uq", our_map.get("user_quote")),
                      ("our_ub", our_map.get("user_base"))):
        info = by.get(pk) if pk else None
        print(f"BAL {label} {pk} owner={(info or {}).get('owner')} amt={tok_amt(info) if info else None}")

    if p:
        print("mint_base", d._pk(p.get("base_mint") or b""),
              "mint_quote", d._pk(p.get("quote_mint") or b""))


if __name__ == "__main__":
    raise SystemExit(main() or 0)
