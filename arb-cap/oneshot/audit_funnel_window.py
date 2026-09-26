#!/usr/bin/env python3
"""Read-only funnel detail for the armed #6 window."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
HURDLE = 525_000


def main() -> int:
    # paper started ~38 min ago; use last 2500s of unix ts gates
    import time
    now = time.time()
    known = searchable = mut = cap_ok = cap_h = would = 0
    fam = Counter()
    proto = Counter()
    cap_vals = []
    mut_rows = []
    search_rows = []
    n = 0
    with AUDIT.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"kind":"gate"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("kind") != "gate":
                continue
            ts = int(rec.get("ts") or 0)
            if ts < now - 2500:
                continue
            n += 1
            proto[rec.get("proto")] += 1
            fam[rec.get("family")] += 1
            if rec.get("known"):
                known += 1
            if rec.get("searchable"):
                searchable += 1
                search_rows.append(rec)
            if rec.get("mut_authoritative"):
                mut += 1
                mut_rows.append(rec)
            g = int(rec.get("cap_gross") or 0)
            if rec.get("cap_pos"):
                cap_ok += 1
                cap_vals.append(g)
            if rec.get("cap_hurdle"):
                cap_h += 1
            if rec.get("would_send_new"):
                would += 1
    print(f"gates_2500s={n} known={known} searchable={searchable} "
          f"cap_pos={cap_ok} cap_hurdle={cap_h} mut_auth={mut} would_new={would}")
    print(f"proto={dict(proto)} family={dict(fam)}")
    if cap_vals:
        cap_vals.sort()
        print(f"cap_gross n={len(cap_vals)} min={cap_vals[0]} p50={cap_vals[len(cap_vals)//2]} "
              f"max={cap_vals[-1]} gt_hurdle={sum(1 for x in cap_vals if x > HURDLE)}")
    print("mut_auth_rows:")
    for r in mut_rows:
        print({
            "idx": r.get("pool_idx"),
            "proto": r.get("proto"),
            "fam": r.get("family"),
            "search": r.get("searchable"),
            "cap": r.get("cap_gross"),
            "gross": r.get("gross"),
            "hurdle": r.get("cap_hurdle"),
            "exec": r.get("exec_fam"),
            "sync": r.get("synced_all"),
            "n_hop": r.get("n_hop"),
            "would": r.get("would_send_new"),
        })
    # searchable cap distribution
    sg = sorted(int(r.get("cap_gross") or 0) for r in search_rows)
    if sg:
        print(f"searchable_cap n={len(sg)} min={sg[0]} p50={sg[len(sg)//2]} max={sg[-1]} "
              f"pos={sum(1 for x in sg if x>0)} gt_hurdle={sum(1 for x in sg if x>HURDLE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
