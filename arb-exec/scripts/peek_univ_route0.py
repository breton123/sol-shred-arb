#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
pools = u.get("pools") or []
print("n_pools", len(pools), "keys", sorted(u.keys())[:20])
print("protos", Counter(str(p.get("proto") or p.get("kind")) for p in pools))
# token pairs
toks = {}
for p in pools:
    t = p.get("token")
    proto = str(p.get("proto") or p.get("kind") or "")
    toks.setdefault(t, set()).add(proto)
r0 = sum(1 for v in toks.values() if "dlmm" in v and "pump" in v)
print("tokens", len(toks), "route0_tokens", r0, "dirs", r0 * 2)
print("sample", {k: pools[0].get(k) for k in list(pools[0])[:12]} if pools else None)
