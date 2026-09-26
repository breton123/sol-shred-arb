#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

live.load_dotenv()
w = "HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"
b = d.rpc("getBalance", [w])
lam = b["value"] if isinstance(b, dict) else b
print("wallet_sol", lam / 1e9)
ex = d.get_multiple(["38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K"])[0]
print("our_exec_lamports", (ex or {}).get("lamports"), "owner", (ex or {}).get("owner"))
so = Path("/home/louis/arb-exec/program/target/deploy/route0.so")
print("route0_so", so.exists(), so.stat().st_size if so.exists() else 0)
print("live_prog", Path("/home/louis/arb-exec-live/program").exists())
print("hops_src", Path("/home/louis/arb-exec/program_hops/src/lib.rs").exists())
print("wallet_json", Path("/home/louis/arb-exec/.deploy/wallet.json").exists())
