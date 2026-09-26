#!/usr/bin/env python3
"""Read-only summary of TRIGGER-011 events. Does not write the capture."""
import json
from collections import Counter
from pathlib import Path

p = Path("/home/louis/captures/trigger011/events.jsonl")
klass = Counter()
outer = Counter()
n = 0
unk = 0
exact = 0
sample_unk = []
with p.open(encoding="utf-8", errors="replace") as f:
    for line in f:
        if '"kind":"trigger011"' not in line and '"trigger011"' not in line:
            # still try parse if kind field differs
            pass
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        n += 1
        k = r.get("klass") or r.get("class") or r.get("state") or "?"
        klass[str(k)] += 1
        oh = r.get("outer_hex") or r.get("outer") or ""
        if k in ("RELEVANT_UNKNOWN", "unk", "unknown") or "UNKNOWN" in str(k).upper():
            unk += 1
            if oh:
                outer[oh[:16]] += 1
            if len(sample_unk) < 3:
                sample_unk.append({x: r.get(x) for x in list(r)[:12]})
        if "EXACT" in str(k).upper():
            exact += 1
print(json.dumps({
    "lines": n,
    "klass": klass.most_common(12),
    "unk": unk,
    "exact": exact,
    "outer_prefixes": outer.most_common(15),
    "sample_keys": list(sample_unk[0]) if sample_unk else [],
    "sample": sample_unk[:1],
}, default=str)[:4000])
