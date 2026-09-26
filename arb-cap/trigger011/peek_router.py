#!/usr/bin/env python3
"""Off-path inspection of highest-value historical router txs.

Does not invent a decoder. Prints outer program, ix data length/prefix,
and whether a supported DEX disc appears in outer data.
"""
from __future__ import annotations

import json
import sys
import urllib.request

from rpc_url import rpc_url

SIGS = [
    # FLASHX $138 late-121 trigger
    "F6GsarBcRvBfDD1k9sEWQUVso44hmSZVMccHUGsSeAUCzt8BCebeQgnP9fqxnGHGywDnYeDRCoJGBHhqCdEbeGB",
    # 6Vo late-121 trigger
    "2ppTmawNzGZ6bVHRLSeKwKKnJuQKMr2HstyHcTGZfz1mkJoajd7qDHQCeQdYTzMHqYEwcfZYp5fecQYUjETrkXCD",
    # DF1ow
    "2b1NgbsW7PWNyijrd5H6QK6MG9gincgAGx3iJjMyJWRE77rzovo9DXpmVy6Sf2fbx5iDwrvNhxmnZAn8CHvU8VCm",
]

PUMP_SELL = "33e685a4017f83ad"
PUMP_BUY_EQ = "c62e1552b4d9e870"
DLMM_SWAP2 = "414b3f4ceb5b5b88"
DLMM_SWAP1 = "f8c69e91e17587c8"
DISCS = {
    PUMP_SELL: "pump_sell",
    PUMP_BUY_EQ: "pump_buy_eq",
    DLMM_SWAP2: "dlmm_swap2",
    DLMM_SWAP1: "dlmm_swap1",
}


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    url = rpc_url()
    for sig in SIGS:
        doc = rpc(url, "getTransaction", [sig, {"encoding": "json", "maxSupportedTransactionVersion": 0}])
        val = doc.get("result")
        if not val:
            print(f"{sig[:12]}  missing")
            continue
        msg = val["transaction"]["message"]
        keys = msg.get("accountKeys") or []
        alts = msg.get("addressTableLookups") or []
        ixs = msg.get("instructions") or []
        meta = val.get("meta") or {}
        inner = meta.get("innerInstructions") or []
        print(f"\n{sig[:16]}  keys={len(keys)} lut={len(alts)} ix={len(ixs)} inner_groups={len(inner)}")
        for i, ix in enumerate(ixs):
            pi = ix.get("programIdIndex")
            data = ix.get("data") or ""
            print(f"  outer[{i}] prog={keys[pi][:12] if pi is not None and pi < len(keys) else pi} "
                  f"data_len={len(data)} data[:24]={data[:24]}")
            low = data.lower()
            for disc, name in DISCS.items():
                if disc in low:
                    print(f"    EMBEDDED {name}")
        for g in inner:
            for ix in g.get("instructions") or []:
                pid = ix.get("programId") or ""
                if "pAMM" in pid or "LBUZ" in pid or pid.endswith("Bay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"):
                    print(f"  inner dex {pid[:12]} parsed={ix.get('parsed', {}).get('type')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
