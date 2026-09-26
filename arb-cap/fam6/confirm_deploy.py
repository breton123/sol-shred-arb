#!/usr/bin/env python3
import sys

sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

live.load_dotenv()
pid = "CnddPhKV1fnKE7ic5nSJcoVq2XFmQ9daE3tuqc2u6qTt"
our = "38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K"
accs = d.get_multiple([pid, our])
for name, a in zip(["hops", "our_exec"], accs):
    print(
        name,
        "exists",
        bool(a),
        "lamports",
        (a or {}).get("lamports"),
        "owner",
        (a or {}).get("owner"),
        "dlen",
        len((a or {}).get("data") or b""),
    )
bal = d.rpc("getBalance", ["HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"])
print("wallet", bal.get("value") if isinstance(bal, dict) else bal)
sig = "2g5nZtwc36FwJrePPdM7tMWYg3bESB52GCzUvzPrQ2E1ynEjz7SgbKVtayeJzXms7GQ8jV1R2AjLcLURfbREJzmK"
tx = d.rpc(
    "getTransaction",
    [sig, {"encoding": "json", "commitment": "confirmed", "maxSupportedTransactionVersion": 1}],
)
print("deploy_tx", bool(tx), "err", (tx.get("meta") or {}).get("err") if tx else None)
