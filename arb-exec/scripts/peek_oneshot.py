#!/usr/bin/env python3
import json
import os
import urllib.request
from pathlib import Path

u = (os.environ.get("HELIUS_RPC_URL") or "").strip()
if not u:
    k = (os.environ.get("HELIUS_API_KEY") or "").strip()
    u = f"https://mainnet.helius-rpc.com/?api-key={k}" if k else ""
print("rpc", int(bool(u)))
if u:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "getBalance",
        "params": ["HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"],
    }).encode()
    req = urllib.request.Request(u, data=body, headers={"Content-Type": "application/json"})
    val = json.loads(urllib.request.urlopen(req, timeout=20).read())["result"]["value"]
    print(f"wallet_sol {val/1e9:.6f}")
p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
lines = [x for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
print("audit_n", len(lines))
for line in lines[-8:]:
    r = json.loads(line)
    a = r.get("arb") or {}
    print(
        f"  pool={(r.get('pool') or '')[:8]} dir={a.get('direction')} "
        f"ain={a.get('amount_in')} gp={a.get('gross')} auth={r.get('auth_slot')}"
    )
univ = Path("/home/louis/captures/paper_orbit/liveuniv.json")
if univ.exists():
    u = json.loads(univ.read_text())
    pools = u.get("pools") or []
    print("univ", u.get("gen"), "n", u.get("n"), "keys", list(pools[0].keys())[:18] if pools else [])
