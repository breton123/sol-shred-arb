#!/usr/bin/env python3
from __future__ import annotations
import json, sys, urllib.request
from b58 import ALPH
from rpc_url import rpc_url

def b58raw(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + ALPH.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    pad = 0
    for ch in s:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + raw.lstrip(b"\x00")

def rpc(url, method, params):
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

sig = "2ppTmawNzGZ6bVHRLSeKwKKnJuQKMr2HstyHcTGZfz1mkJoajd7qDHQCeQdYTzMHqYEwcfZYp5fecQYUjETrkXCD"
url = rpc_url()
doc = rpc(url, "getTransaction", [sig, {"encoding":"jsonParsed","maxSupportedTransactionVersion":0}])
val = doc["result"]
msg = val["transaction"]["message"]
ixs = msg["instructions"]
print("outer 6Vo data bytes:")
for ix in ixs:
    if str(ix.get("programId","")).startswith("6Vo"):
        data = ix.get("data") or ""
        raw = b58raw(data)
        print("len", len(raw), "hex", raw.hex())
        if len(raw) >= 16:
            print("u64[0]", int.from_bytes(raw[:8],"little"))
            print("u64[1]", int.from_bytes(raw[8:16],"little") if len(raw)>=16 else None)
        print("accounts", [a.get("pubkey") if isinstance(a, dict) else a for a in ix.get("accounts") or []][:16])
meta = val.get("meta") or {}
for g in meta.get("innerInstructions") or []:
    for ix in g.get("instructions") or []:
        pid = ix.get("programId") or ""
        parsed = ix.get("parsed")
        if "pAMM" in pid or pid.startswith("LBUZ") or parsed:
            print("inner", pid[:20], parsed or ix.get("data","")[:40])
