#!/usr/bin/env python3
from auth_ro import latest, n_pools, open_ro, parse_dlmm, PROTO_DLMM
from dlmm_quote import fee_after_time, next_boundaries
import json, time
from pathlib import Path

univ = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
pools = univ["pools"]
mm = open_ro()
n = n_pools(mm)
now = int(time.time())
print("n", n, "now", now)
sched = 0
shown = 0
for i in range(min(n, len(pools))):
    row = latest(mm, i)
    if not row or row["proto"] != PROTO_DLMM:
        continue
    d = parse_dlmm(row["blob"])
    if not d:
        continue
    b = next_boundaries(d, now)
    r0, a0, f0 = fee_after_time(d, now)
    if b:
        sched += 1
        ts = b[0][1]
        r1, a1, f1 = fee_after_time(d, ts)
        if shown < 8:
            print(
                f"idx={i} {pools[i]['pubkey'][:8]} last={d.last_upd} "
                f"fp={d.filter_period} dp={d.decay_period} rf={d.reduction_factor} "
                f"vacc={d.vol_acc} vfc={d.variable_fee_control} "
                f"bounds={b} fee_now={r0} fee@{b[0][0]}={r1} dfee={r1-r0}"
            )
            shown += 1
print("dlmm_with_future_boundary", sched)
