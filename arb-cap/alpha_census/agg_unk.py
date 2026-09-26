#!/usr/bin/env python3
"""Cluster RELEVANT_UNKNOWN outers. Read-only."""
import json
from collections import Counter
from pathlib import Path

ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = ALPH[r] + out
    pad = 0
    for b in raw:
        if b == 0:
            pad += 1
        else:
            break
    return "1" * pad + (out or "1")

p = Path("/home/louis/captures/trigger011/events.jsonl")
outer = Counter()
pools = Counter()
n5 = 0
shown = False
with p.open(encoding="utf-8", errors="replace") as f:
    for line in f:
        if '"klass":5' not in line and '"klass": 5' not in line:
            continue
        r = json.loads(line)
        if int(r.get("klass") or -1) != 5:
            continue
        n5 += 1
        if not shown:
            print("KEYS", sorted(r.keys()))
            shown = True
        oh = r.get("outer_hex") or r.get("outer") or ""
        if isinstance(oh, str) and len(oh) >= 64:
            try:
                outer[b58(bytes.fromhex(oh[:64]))] += 1
            except ValueError:
                outer[oh[:16]] += 1
        elif oh:
            outer[str(oh)[:44]] += 1
        else:
            outer["(none)"] += 1
        pools[str(r.get("pool0") or r.get("n_watch") or "")] += 1
print("n5", n5)
print("TOP_OUTER")
for k, v in outer.most_common(20):
    print(f"{v:6} {k}")
print("TOP_POOL_OR_WATCH")
for k, v in pools.most_common(8):
    print(f"{v:6} {k}")
