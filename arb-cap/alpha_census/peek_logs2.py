#!/usr/bin/env python3
import json
import census

DLMM = census.DLMM
sig = "E33aj7HWiJi8XHwqzWzkMsBzM349kMd2KxYFky5DzjvHg17DLCPoCx7KQxKQaosd5MHMjXGMoUBucWwWGj2vrwC"
tx = census.fetch_tx(census.shyft(), sig)
meta = tx.get("meta") or {}
msg = (tx.get("transaction") or {}).get("message") or {}
keys = msg.get("accountKeys") or []
print("nkeys", len(keys), "nlogs", len(meta.get("logMessages") or []), "err", meta.get("err"))
print("LOGS")
for line in meta.get("logMessages") or []:
    print(line[:200])
print("dlmm in keys", DLMM in keys)
print("outer ixs", len(msg.get("instructions") or []))
# program indexes
for ix in msg.get("instructions") or []:
    idx = ix.get("programIdIndex")
    pid = keys[idx] if isinstance(idx, int) and idx < len(keys) else "?"
    data = ix.get("data") or ""
    print(" ix", pid, "data_len", len(data))
