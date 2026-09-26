#!/usr/bin/env python3
import json
from pathlib import Path
p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
last = None
for line in p.open():
    if "send_quote" in line:
        last = json.loads(line)
if not last:
    print("none")
else:
    print(json.dumps({
        "pool": (last.get("pool") or "")[:16],
        "n": last.get("n"),
        "n_ix": last.get("n_ix"),
        "shred": last.get("shred"),
        "send_quote": last.get("send_quote"),
        "arb": last.get("arb"),
    }, indent=2))
