#!/usr/bin/env python3
"""Family-255 typed-sequence breakdown. Read-only."""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
HURDLE = 525_000


def main() -> int:
    now = time.time()
    seq_all = Counter()
    seq_search = Counter()
    seq_mut = Counter()
    seq_cap = Counter()
    seq_gross = defaultdict(int)
    seq_capg = defaultdict(int)
    seq_n = defaultdict(int)
    mut_detail = []
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
            if ts < now - 2700:
                continue
            seq = rec.get("seq") or "?"
            hop = int(rec.get("n_hop") or 0)
            key = f"{seq}|h{hop}|fam{rec.get('family')}"
            seq_all[key] += 1
            if rec.get("searchable"):
                seq_search[key] += 1
                seq_n[key] += 1
                seq_gross[key] += int(rec.get("gross") or 0)
                seq_capg[key] += int(rec.get("cap_gross") or 0)
            if rec.get("mut_authoritative"):
                seq_mut[key] += 1
                mut_detail.append({
                    "seq": seq,
                    "hop": hop,
                    "fam": rec.get("family"),
                    "idx": rec.get("pool_idx"),
                    "cap": rec.get("cap_gross"),
                    "gross": rec.get("gross"),
                    "sync": rec.get("synced_all"),
                    "exec": rec.get("exec_fam"),
                })
            if rec.get("cap_pos"):
                seq_cap[key] += 1
    print("ALL_GATES")
    for k, n in seq_all.most_common(20):
        print(f"  {n:5} {k}")
    print("SEARCHABLE")
    for k, n in seq_search.most_common(20):
        print(f"  {n:5} {k}  sum_gross={seq_gross[k]} sum_cap={seq_capg[k]}")
    print("MUT_AUTH")
    for k, n in seq_mut.most_common(20):
        print(f"  {n:5} {k}")
    print("CAP_POS")
    for k, n in seq_cap.most_common(20):
        print(f"  {n:5} {k}")
    print("MUT_DETAIL")
    for r in mut_detail:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
