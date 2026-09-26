#!/usr/bin/env python3
"""Last-hour paper_orbit audit: frames, gates, slots. No send."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
WINDOW = 3600


def main() -> int:
    now = int(time.time())
    t0 = now - WINDOW
    t0_ns = t0 * 1_000_000_000
    kinds = {}
    frame_class = {}
    gates = {
        "n": 0, "known": 0, "searchable": 0, "gross_pos": 0, "cap_pos": 0,
        "cap_hurdle": 0, "exec_fam": 0, "would_new": 0, "gross_sum": 0, "cap_sum": 0,
    }
    slots = set()
    frame_slots = set()
    unknown = 0
    ts_min = None
    ts_max = None
    with AUDIT.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line[:1] != "{":
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = r.get("kind")
            ts = r.get("ts")
            t_ns = r.get("t0_ns") or r.get("now_ns")
            in_win = False
            if isinstance(ts, int) and ts >= t0:
                in_win = True
                stamp = ts
            elif isinstance(t_ns, int) and t_ns >= t0_ns:
                in_win = True
                stamp = t_ns // 1_000_000_000
            if not in_win:
                continue
            kinds[kind] = kinds.get(kind, 0) + 1
            ts_min = stamp if ts_min is None else min(ts_min, stamp)
            ts_max = stamp if ts_max is None else max(ts_max, stamp)
            if kind == "frame":
                frame_class[r.get("class")] = frame_class.get(r.get("class"), 0) + 1
                slot = ((r.get("shred") or {}).get("slot")) or 0
                if slot:
                    frame_slots.add(slot)
            elif kind == "gate":
                gates["n"] += 1
                gates["known"] += int(bool(r.get("known")))
                gates["searchable"] += int(bool(r.get("searchable")))
                gates["gross_pos"] += int(bool(r.get("gross_pos")))
                gates["cap_pos"] += int(bool(r.get("cap_pos")))
                gates["cap_hurdle"] += int(bool(r.get("cap_hurdle")))
                gates["exec_fam"] += int(bool(r.get("exec_fam")))
                gates["would_new"] += int(bool(r.get("would_send_new")))
                if r.get("gross_pos"):
                    gates["gross_sum"] += int(r.get("gross") or 0)
                if r.get("cap_hurdle"):
                    gates["cap_sum"] += int(r.get("cap_gross") or 0)
                if r.get("shred_slot"):
                    slots.add(int(r["shred_slot"]))
            elif kind == "unknown_pool":
                unknown += 1
    doc = {
        "now": now,
        "t0": t0,
        "span": [ts_min, ts_max],
        "kinds": kinds,
        "frame_class": frame_class,
        "gates": gates,
        "gate_slots": len(slots),
        "frame_slots": len(frame_slots),
        "unknown_pool": unknown,
    }
    slot_path = Path("/tmp/our_slots.json")
    slot_path.write_text(json.dumps(sorted(frame_slots | slots)), encoding="utf-8")
    print(json.dumps(doc))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
