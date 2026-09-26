#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

p = Path("/home/louis/arb-cap/oneshot/ENTRY_TRUTH.json")
rep = json.loads(p.read_text())
print("summary", json.dumps(rep["summary"], indent=2))
print("by_class_outcome")
c = Counter((x["class"], x.get("outcome")) for x in rep["cases"])
for k, n in c.most_common():
    print(n, k)
# #4
n4 = "92ecff4c9a09dfa5"
landed = [x for x in rep["cases"] if x.get("outcome") == "landed-success"]
print("landed", len(landed))
for x in landed:
    print(json.dumps({k: x.get(k) for k in ("class", "sig_hex", "shred", "batch_seen", "batch_ok", "batch_gap", "entry_hit", "dt_ns")}))
frag = [x for x in rep["cases"] if x["class"] == "FRAGMENT_ONLY"]
print("fragment_sample")
for x in frag[:5]:
    print(json.dumps({k: x.get(k) for k in ("class", "outcome", "shred", "batch_seen", "batch_ok", "batch_gap")}))
print("n4", [x for x in rep["cases"] if x["sig_hex"].startswith(n4)])
