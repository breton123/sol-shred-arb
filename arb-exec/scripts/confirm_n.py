#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
sys.path.insert(0, "/home/louis/arb-cap/paper004")
import live001 as live
import paper004 as p4

N = "3WzxXps9gBMijAxsvUcaSwJYwBq385s2wwLwCU23JSSLXvrsoTuJfHUDKAQfmCWYXG89nmjmYxAETyLxw3E8UtmM"
OURS = "3q6BM1m6EJkLVvXBbF8haSMnk6msVCY7U1awYoX96ufodD8byML3Nhct2k267cqsrxWafwTeFG2k1HWENbvDg2kr"
MUTS = [
    "4MSAU6vqWpkGr7KJ",
    "uLE3HxjQ6MUvBnfW",
    "5Kvn2GtGiGd1nSPf",
]


def main():
    live.load_dotenv()
    res = json.loads(Path("/home/louis/arb-cap/oneshot/RESULT.json").read_text())
    stale = json.loads(Path("/home/louis/arb-cap/oneshot/STALE.json").read_text())
    fire = res.get("fire") or {}
    print("n_from_stale", stale.get("n_sig"))
    print("opp_n", json.dumps(res.get("opp", {}).get("n")))
    print("auth_slot", (res.get("opp") or {}).get("auth_slot"))
    st = p4.rpc("getSignatureStatuses", [[N, OURS], {"searchTransactionHistory": True}], pause=0.3)
    print("statuses", st)
    # resolve full mut sigs from stale intervening
    for x in stale.get("intervening") or []:
        if x.get("kind") != "pool_mutation":
            continue
        sig = x["sig"]
        tx = p4.fetch_tx(sig)
        if not tx:
            print("mut missing", sig[:16])
            continue
        keys = p4.tx_keys(tx)
        pids = p4.ix_pids(tx)
        print(
            f"mut idx={x['tx_index']} slot={tx.get('slot')} "
            f"dlmm={fire.get('dlmm') in keys} pump={fire.get('pump') in keys} "
            f"both_prog={('LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo' in pids and 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA' in pids)} "
            f"err={tx.get('meta', {}).get('err')} searcher={keys[0][:8] if keys else ''} "
            f"sig={sig}"
        )
    # search trigger pool for N
    opp = res.get("opp") or {}
    pool_hex = opp.get("pool") or ""
    pool = p4.hex_pk(pool_hex) if pool_hex and len(pool_hex) == 64 else pool_hex
    print("trigger_pool", pool)
    if pool:
        sigs = p4.rpc("getSignaturesForAddress", [pool, {"limit": 20}], pause=0.3) or []
        for ent in sigs:
            print("  pool_sig", ent.get("slot"), ent.get("err"), (ent.get("signature") or "")[:20])


if __name__ == "__main__":
    raise SystemExit(main() or 0)
