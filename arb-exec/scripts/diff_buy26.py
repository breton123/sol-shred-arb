#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
BUYQ = bytes.fromhex("c62e1552b4d9e870")
PAIR = "BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs"
SIG = "64rckXkiJmdSHjBH"


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


def first_buy():
    live.load_dotenv()
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


def main():
    sig, live_accs, data = first_buy()
    print(f"live_sig={sig} n={len(live_accs)} dlen={len(data)} data={data.hex()}")
    names = [
        "pool", "user", "global", "base_mint", "quote_mint",
        "user_base", "user_quote", "pool_base", "pool_quote",
        "proto_fee", "proto_fee_ata", "t22", "keg", "sys", "ata",
        "event", "pump", "coin_creator_vault_ata", "coin_creator_vault_auth",
        "gvol", "uvol", "fee_cfg", "fee_prog", "pool_v2", "fee_rec", "fee_ata",
    ]
    our = json.loads(Path("/home/louis/arb-cap/exec_live002b/report.json").read_text())
    ours = our.get("pump_buy_accounts") or our.get("accounts") or []
    print("report_keys", sorted(our.keys()))
    # fallback: dump from alt.json + known compile
    alt = {}
    ap = Path("/home/louis/arb-cap/exec_live002b/alt.json")
    if ap.exists():
        alt = json.loads(ap.read_text())
        print("alt", alt.get("address"), "n", len(alt.get("addresses") or []))
    if live_accs:
        for i, a in enumerate(live_accs):
            lab = names[i] if i < len(names) else f"#{i}"
            print(f"  live[{i:02d}] {lab:24s} {a}")


if __name__ == "__main__":
    raise SystemExit(main() or 0)
