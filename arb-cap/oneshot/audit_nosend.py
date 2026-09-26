#!/usr/bin/env python3
"""Read-only: why ONESHOT#6 seen=0. Does not arm/disarm/send."""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
STATS = Path("/home/louis/captures/paper_orbit/stats.json")
PLANE = Path("/home/louis/arb-exec/.deploy/alt_plane.json")
S008 = Path("/home/louis/captures/state008/READY")
S007 = Path("/home/louis/captures/state007/READY")
WINDOW = 2400


def main() -> int:
    now = time.time()
    print(
        f"ARMED={Path('/home/louis/arb-cap/oneshot/ARMED').exists()} "
        f"STATE008_READY={S008.exists()} STATE007_ALIAS={S007.exists()}"
    )
    print(f"audit_size={AUDIT.stat().st_size} mtime_age={int(now - AUDIT.stat().st_mtime)}s")
    plane = {}
    if PLANE.exists():
        plane = json.loads(PLANE.read_text(encoding="utf-8"))
    print(f"plane_keys={len(plane)}")

    kinds = Counter()
    frames = Counter()
    race = Counter()
    mut = Counter()
    would = Counter()
    cap = Counter()
    proto = Counter()
    drop_s007 = 0
    drop_upd = 0
    drop_plane = 0
    opp_recent = 0
    framed_rr = 0
    gate_recent = 0
    last_opp = None
    last_gate = None
    last_fresh = None
    fat = []

    sz = AUDIT.stat().st_size
    with AUDIT.open("rb") as f:
        if sz > 80_000_000:
            f.seek(sz - 80_000_000)
            f.readline()
        for raw in f:
            if b'"kind":' not in raw:
                continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            k = rec.get("kind")
            kinds[k] += 1
            ts = rec.get("ts") or 0
            recent = True
            if isinstance(ts, (int, float)) and ts > 1e12:
                recent = (now - ts / 1e9) < WINDOW
            elif isinstance(ts, (int, float)) and ts > 1e9:
                recent = (now - ts) < WINDOW
            if k == "opp_synced":
                last_opp = rec
                if recent:
                    opp_recent += 1
                    fr = (rec.get("frame") or {}).get("class")
                    frames[fr] += 1
                    race[rec.get("race_ready")] += 1
                    proto[rec.get("proto") or (rec.get("n") or {}).get("proto")] += 1
                    if fr == "framed" and rec.get("race_ready") == 1:
                        framed_rr += 1
                        pool = str(rec.get("pool") or "")
                        if pool not in plane:
                            drop_plane += 1
                        sq = rec.get("send_quote") or {}
                        g = int(sq.get("cap_gross") or (rec.get("arb") or {}).get("gross") or 0)
                        fat.append((g, pool[:8], rec.get("race_ready"), sq.get("cap_ok")))
            elif k == "gate":
                last_gate = rec
                if recent:
                    gate_recent += 1
                    mut[bool(rec.get("mut_authoritative"))] += 1
                    would[bool(rec.get("would_send_new"))] += 1
                    cap[bool(rec.get("cap_hurdle"))] += 1
                    if rec.get("s007_ready") == 0:
                        drop_s007 += 1
                    if rec.get("updating"):
                        drop_upd += 1
            elif k == "fresh_drop":
                last_fresh = rec

    print(f"kinds={dict(kinds)}")
    print(f"opp_recent={opp_recent} framed_race_ready={framed_rr} plane_miss={drop_plane}")
    print(f"frames={dict(frames)} race_ready={dict(race)} proto={dict(proto)}")
    print(f"gate_recent={gate_recent} mut_auth={dict(mut)} would_new={dict(would)} cap_hurdle={dict(cap)}")
    print(f"gate s007_ready0={drop_s007} updating={drop_upd}")
    if fat:
        fat.sort(reverse=True)
        print("top_framed_rr", fat[:8])
    if last_opp:
        print("last_opp", {
            "pool": last_opp.get("pool"),
            "race_ready": last_opp.get("race_ready"),
            "frame": last_opp.get("frame"),
            "gross": (last_opp.get("arb") or {}).get("gross"),
            "cap": (last_opp.get("send_quote") or {}).get("cap_gross"),
        })
    if last_gate:
        keep = {k: last_gate.get(k) for k in last_gate if k != "sig_hex"}
        print("last_gate", keep)
    if last_fresh:
        print("last_fresh_drop", last_fresh)
    if STATS.exists():
        s = json.loads(STATS.read_text(encoding="utf-8"))
        interesting = {k: s[k] for k in s if any(x in k for x in (
            "opp", "frame", "s007", "fresh", "sync", "ready"
        ))}
        print("stats", interesting or list(s)[:20])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
