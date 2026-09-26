#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
pools = u.get("pools") or []
routes = u.get("routes") or []
print("pools", len(pools), "routes", len(routes))
fam = {}
for r in routes:
    fam[int(r.get("family") or 255)] = fam.get(int(r.get("family") or 255), 0) + 1
print("route_families", fam)
for i in (32, 49, 146, 147, 160, 167):
    if i < len(pools):
        p = pools[i]
        print(i, {k: p.get(k) for k in ("proto", "kind", "pubkey", "token", "family") if k in p or True})
        print("  ", {k: p.get(k) for k in list(p)[:12]})
