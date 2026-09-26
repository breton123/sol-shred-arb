#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
BUYQ = bytes.fromhex("c62e1552b4d9e870")
PAIR = "BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs"


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


def main():
    live.load_dotenv()
    for addr, lim in ((PAIR, 20), (PUMP, 15)):
        sigs = d.rpc("getSignaturesForAddress", [addr, {"limit": lim}]) or []
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
                accs = ix_accounts(ix, keys)
                print(
                    f"sig={ent['signature'][:16]} n={len(accs)} dlen={len(data)} "
                    f"u64s={list(__import__('struct').unpack_from('<'+'Q'*((len(data)-8)//8), data, 8))} "
                    f"tail={data[8+8*((len(data)-8)//8):].hex()} pool={accs[0][:8]}"
                )
                print("  last6", [a[:8] for a in accs[-6:]])
                return
    print("no buy_exact_quote_in found")


if __name__ == "__main__":
    raise SystemExit(main() or 0)
