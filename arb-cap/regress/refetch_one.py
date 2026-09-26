#!/usr/bin/env python3
"""Re-fetch one historical trigger and compare to stored bytes. Does not print the RPC URL."""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path

import hist_funnel as h

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.strip().startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

url = os.environ.get("HELIUS_RPC_URL") or os.environ.get("RPC_URL")
if not url and os.environ.get("HELIUS_API_KEY"):
    url = "https://mainnet.helius-rpc.com/?api-key=" + os.environ["HELIUS_API_KEY"]
if not url:
    raise SystemExit("no rpc url")

SIG = "F6GsarBcRvBfDD1k9sEWQUVso44hmSZVMccHUGsSeAUCzt8BCebeQgnP9fqxnGHGywDnYeDRCoJGBHhqCdEbeGB"
body = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getTransaction",
    "params": [SIG, {"encoding": "base64", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}],
}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=40) as r:
    resp = json.loads(r.read().decode())
if resp.get("error"):
    raise SystemExit("rpc error " + json.dumps(resp["error"])[:200])
tx = ((resp.get("result") or {}).get("transaction"))
if not isinstance(tx, list) or not tx:
    raise SystemExit("no base64 tx")
raw = base64.b64decode(tx[0])
parsed = h.parse_tx(raw)
print("fresh_len", len(raw), "head", raw[:8].hex(), "klass", parsed["klass"], "why", parsed["why"], "pools", len(parsed["pools"]))
static = [p for p in parsed["pools"] if p.get("pk")]
print("static", [(p["proto"], p["why"], p["pk"][:8], p["amount"]) for p in static[:4]])
