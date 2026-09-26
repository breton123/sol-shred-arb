#!/usr/bin/env python3
import json
import census

sig = "E33aj7HWiJi8XHwqzWzkMsBzM349kMd2KxYFky5DzjvHg17DLCPoCx7KQxKQaosd5MHMjXGMoUBucWwWGj2vrwC"
tx = census.fetch_tx(census.shyft(), sig)
meta = (tx or {}).get("meta") or {}
logs = meta.get("logMessages") or []
print("nlogs", len(logs), "err", meta.get("err"), "keys", list(tx)[:8] if isinstance(tx, dict) else type(tx))
for line in logs:
    if "Instruction" in line or "invoke" in line or "LBUZ" in line or "pAMM" in line:
        print(line[:180])
