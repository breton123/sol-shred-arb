#!/usr/bin/env python3
"""Gross vs 0.05-cap on last-hour positive gates. Also locate frame timestamps."""
from __future__ import annotations

import json
import time
from pathlib import Path

AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
now = int(time.time())
t0 = now - 3600
pos = []
last_frame = None
frame_n = 0
with AUDIT.open("r", encoding="utf-8", errors="replace") as f:
    for line in f:
        if '"kind":"gate"' in line:
            r = json.loads(line)
            if int(r.get("ts") or 0) < t0:
                continue
            if r.get("gross_pos"):
                pos.append((int(r.get("gross") or 0), int(r.get("cap_gross") or 0), int(r.get("cap_pos") or 0), int(r.get("cap_hurdle") or 0), r.get("proto"), r.get("family"), r.get("shred_slot")))
        elif '"kind":"frame"' in line:
            frame_n += 1
            last_frame = line[:240]

print("frame_lines_in_file", frame_n)
print("last_frame", last_frame)
print("gross_pos", len(pos))
pos.sort()
if pos:
    gs = [p[0] for p in pos]
    cs = [p[1] for p in pos]
    print("optimum_lamports min/p50/max", gs[0], gs[len(gs)//2], gs[-1])
    print("cap_lamports min/p50/max", cs[0], cs[len(cs)//2], cs[-1])
    print("optimum_SOL sum", sum(gs)/1e9, "cap_SOL sum", sum(cs)/1e9)
    print("cap_pos", sum(p[2] for p in pos), "cap_hurdle", sum(p[3] for p in pos))
    print("top5 optimum_SOL / cap_SOL")
    for g, c, cp, ch, proto, fam, slot in sorted(pos, reverse=True)[:8]:
        print(f"  opt={g/1e9:.4f} cap={c/1e9:.6f} cap_pos={cp} hurdle={ch} proto={proto} fam={fam} slot={slot}")
