#!/usr/bin/env python3
"""Replay recon.bin AUTH through the timer-decay experiment. Read-only."""
from __future__ import annotations

import heapq
import json
import os
import struct
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from auth_ro import parse_dlmm, parse_pump
from dlmm_quote import cycle_quote, fee_after_time, hurdle, next_boundaries

FIXED = 80
AUTH, INV = 3, 4
PROTO_DLMM, PROTO_PUMP = 1, 2
NOW_LO, NOW_HI = 1_790_300_000, 1_790_400_000
WSOL = "So11111111111111111111111111111111111111112"
SIZES = [int(x * 1_000_000_000) for x in (0.05, 0.10, 0.25, 0.50, 1.0, 2.0, 5.0)]
SIZE_LABEL = ["0.05", "0.10", "0.25", "0.50", "1", "2", "5"]
SEARCHERS = {
    "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X": "Mriya",
    "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK": "4BQ",
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "Dtvmxr",
    "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu": "7dGrdJ",
    "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd": "gtagyE",
    "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4": "9EwQoN",
}
MEV = "https://mev.live/api/arb-explorer/search"
OUT = Path(os.environ.get("TIMER_OUT", "/tmp/timer_decay_replay"))
UNIV171 = Path(os.environ.get("UNIV171", "/home/louis/research/timer_decay/univ171.json"))
UNIV645 = Path(os.environ.get("UNIV645", "/home/louis/captures/paper_orbit/liveuniv.json"))
RECON = Path(os.environ.get("RECON", "/home/louis/captures/paper_orbit/recon.bin"))


def load_pools(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc["pools"]


def partners(pools: list[dict], idx: int) -> list[dict]:
    if idx >= len(pools):
        return []
    d = pools[idx]
    if d.get("proto") != "dlmm" or d.get("my") != WSOL:
        return []
    token = d.get("token") or d.get("mx")
    return [
        p for p in pools
        if p.get("proto") == "pump" and (p.get("token") or p.get("mx")) == token
    ]


def iter_recs(path: Path):
    with path.open("rb") as f:
        hdr = f.read(8)
        if len(hdr) < 8 or struct.unpack_from("<I", hdr)[0] != 0x36305453:
            raise RuntimeError("bad recon magic")
        while True:
            raw = f.read(4)
            if len(raw) < 4:
                break
            ln = struct.unpack("<I", raw)[0]
            if ln < FIXED or ln > 5000:
                break
            blob = f.read(ln)
            if len(blob) < ln:
                break
            kind, proto, _pad, idx = struct.unpack_from("<BBHI", blob, 0)
            slot = struct.unpack_from("<Q", blob, 72)[0]
            body = blob[FIXED:]
            yield kind, proto, idx, slot, body


def eval_routes(dlmm, pumps, now_ts: int) -> list[dict]:
    rows = []
    for meta, pump in pumps:
        for direction in (0, 1):
            h = hurdle(direction)
            best = None
            by_size = []
            for lab, ain in zip(SIZE_LABEL, SIZES):
                out = cycle_quote(dlmm, pump, ain, direction, now_ts)
                if out is None:
                    by_size.append({"size": lab, "gross": None, "net": None})
                    continue
                gross = int(out) - ain
                net = gross - h
                rec = {"size": lab, "gross": gross, "net": net}
                by_size.append(rec)
                if best is None or net > best["net"]:
                    best = rec
            rows.append({
                "pump": meta.get("pubkey"),
                "pump_idx": meta.get("idx"),
                "route": "dlmm-pump" if direction == 0 else "pump-dlmm",
                "direction": direction,
                "best": best,
                "sizes": by_size,
            })
    return rows


def mev_hits(t0: int, t1: int) -> list[dict]:
    rows = []
    t = t0
    while t < t1:
        w1 = min(t + 8, t1)
        body = json.dumps({
            "sort_by": "time", "sort_dir": "asc",
            "time_from": t, "time_to": w1,
            "recent_mint_window_secs": 0, "page_size": 100,
        }).encode()
        req = urllib.request.Request(MEV, data=body, headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                doc = json.loads(r.read().decode())
        except Exception:
            t = w1
            continue
        rows.extend(doc.get("rows") or [])
        t = w1
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    u171 = load_pools(UNIV171)
    u645 = load_pools(UNIV645)
    switched = False
    last_dlmm: dict[int, dict] = {}
    last_pump: dict[int, dict] = {}
    heap: list = []
    seq = 0
    dead = set()
    fired = []
    opens = []
    watching: dict[int, list] = defaultdict(list)
    n_auth = n_sched = 0
    t0 = t1 = None
    clock = 0
    t_run = time.time()

    def univ():
        return u645 if switched else u171

    def cancel(idx: int) -> None:
        dead.update(id(j) for _, _, j in heap if j["pool_idx"] == idx and not j.get("fired"))

    def fire_upto(ts: int) -> None:
        while heap and heap[0][0] <= ts:
            bts, _, job = heapq.heappop(heap)
            if id(job) in dead or job.get("fired"):
                continue
            job["fired"] = True
            d = job["dlmm"]
            fee1, vacc1, vref1 = fee_after_time(d, job["boundary"])
            fee0 = job["fee_before"]
            rec = {
                "pool": job["pool"],
                "pool_idx": job["pool_idx"],
                "token": job["token"],
                "era": job["era"],
                "scheduled_at": job["sched_ts"],
                "decay_boundary": job["boundary"],
                "kind": job["kind"],
                "survived_to_boundary": True,
                "event_at_cross": False,
                "fee_before": fee0,
                "fee_after": fee1,
                "fee_delta": fee1 - fee0,
                "vol_acc_before": job["vol_acc_before"],
                "vol_acc_after": vacc1,
                "partner_untouched": True,
                "crossed_hurdle": False,
                "crosses": [],
                "univ_n": job["univ_n"],
            }
            pumps = []
            for meta, pump, p_ts in job["pumps"]:
                lp = last_pump.get(meta["idx"])
                if lp and lp["ts"] > job["sched_ts"] and lp["ts"] <= job["boundary"]:
                    rec["partner_untouched"] = False
                else:
                    pumps.append((meta, pump))
            if fee1 != fee0 and pumps:
                e0 = eval_routes(d, pumps, job["sched_ts"])
                e1 = eval_routes(d, pumps, job["boundary"])
                by0 = {(r["pump_idx"], r["direction"]): r for r in e0}
                crosses = []
                for r1 in e1:
                    r0 = by0.get((r1["pump_idx"], r1["direction"]))
                    if not r0:
                        continue
                    for a, b in zip(r0["sizes"], r1["sizes"]):
                        if a["net"] is None or b["net"] is None:
                            continue
                        if a["net"] <= 0 < b["net"]:
                            crosses.append({
                                "route": r1["route"],
                                "pump": r1["pump"],
                                "size": b["size"],
                                "net_before": a["net"],
                                "net_after": b["net"],
                                "gross_before": a["gross"],
                                "gross_after": b["gross"],
                            })
                rec["crosses"] = crosses
                rec["crossed_hurdle"] = bool(crosses)
                if crosses:
                    best = max(crosses, key=lambda x: x["net_after"])
                    rec.update({
                        "route": best["route"],
                        "size": best["size"],
                        "net_before": best["net_before"],
                        "net_after": best["net_after"],
                        "gross_before": best["gross_before"],
                        "gross_after": best["gross_after"],
                        "follow": "WATCH",
                        "time_open": None,
                        "subsequent_taker": None,
                        "known_searcher": None,
                    })
                    opens.append(rec)
                    watching[job["pool_idx"]].append(rec)
            fired.append(rec)

    for kind, proto, idx, slot, body in iter_recs(RECON):
        if idx > 170:
            switched = True
        ts = None
        if kind == AUTH and proto == PROTO_DLMM and len(body) >= 71:
            now = struct.unpack_from("<q", body, 63)[0]
            if NOW_LO <= now <= NOW_HI:
                ts = now
        if ts is None:
            if not clock:
                continue
            ts = clock
        if ts < clock:
            ts = clock
        clock = ts
        if t0 is None:
            t0 = ts
        t1 = ts
        fire_upto(ts)
        if kind == INV:
            cancel(idx)
            last_dlmm.pop(idx, None)
            for rec in watching.pop(idx, []):
                if rec.get("follow") == "WATCH":
                    rec["follow"] = "STATE_UNCERTAIN"
                    rec["time_open"] = ts - rec["decay_boundary"]
            continue
        if kind != AUTH:
            continue
        n_auth += 1
        if proto == PROTO_PUMP:
            p = parse_pump(body)
            if p:
                last_pump[idx] = {"ts": ts, "pump": p, "slot": slot}
            continue
        if proto != PROTO_DLMM:
            continue
        d = parse_dlmm(body)
        if d is None:
            continue
        cancel(idx)
        for rec in watching.pop(idx, []):
            if rec.get("follow") == "WATCH":
                rec["follow"] = "NATURALLY_CLOSED_BY_FLOW"
                rec["time_open"] = ts - rec["decay_boundary"]
                rec["closed_slot"] = slot
        last_dlmm[idx] = {"ts": ts, "dlmm": d}
        pools = univ()
        parts = []
        for meta in partners(pools, idx):
            lp = last_pump.get(meta["idx"])
            if lp:
                parts.append((meta, lp["pump"], lp["ts"]))
        if not parts:
            continue
        fee0, vacc0, vref0 = fee_after_time(d, ts)
        for kind_b, bts in next_boundaries(d, ts):
            if bts <= ts:
                continue
            seq += 1
            n_sched += 1
            job = {
                "pool": pools[idx]["pubkey"] if idx < len(pools) else str(idx),
                "pool_idx": idx,
                "token": (pools[idx].get("token") if idx < len(pools) else None),
                "era": "u645" if switched else "u171",
                "univ_n": len(pools),
                "sched_ts": ts,
                "boundary": bts,
                "kind": kind_b,
                "dlmm": d,
                "pumps": parts,
                "fee_before": fee0,
                "vol_acc_before": vacc0,
            }
            heapq.heappush(heap, (bts, seq, job))

    fire_upto(clock)
    for recs in watching.values():
        for rec in recs:
            if rec.get("follow") == "WATCH":
                rec["follow"] = "STILL_OPEN"
                rec["time_open"] = (t1 or clock) - rec["decay_boundary"]

    if opens and len(opens) <= 250:
        print(f"mev join {len(opens)} openings", flush=True)
        by_mint = defaultdict(list)
        tmin = min(o["decay_boundary"] for o in opens) - 2
        tmax = max((o["decay_boundary"] + (o.get("time_open") or 0)) for o in opens) + 8
        tmax = min(tmax, tmin + 6 * 3600)
        for a in mev_hits(int(tmin), int(tmax)):
            if a.get("two_leg_arb_mint"):
                by_mint[a["two_leg_arb_mint"]].append(a)
        for rec in opens:
            close = rec["decay_boundary"] + (rec.get("time_open") or 30)
            hits = [
                a for a in by_mint.get(rec.get("token") or "", [])
                if rec["decay_boundary"] <= int(a.get("time") or 0) <= close
            ]
            if hits:
                rec["subsequent_taker"] = hits[0].get("signature")
                rec["known_searcher"] = SEARCHERS.get(hits[0].get("user") or "", hits[0].get("user"))
                if rec.get("follow") in ("STILL_OPEN", "WATCH", "NATURALLY_CLOSED_BY_FLOW"):
                    rec["follow"] = (
                        "CAPTURED_KNOWN_ARB"
                        if rec["known_searcher"] in SEARCHERS.values()
                        else "CAPTURED_UNKNOWN_SEARCHER"
                    )

    with (OUT / "LEDGER.jsonl").open("w", encoding="utf-8") as f:
        for rec in fired:
            f.write(json.dumps(rec, default=str) + "\n")
    with (OUT / "TIMER_DECAY_OPEN.jsonl").open("w", encoding="utf-8") as f:
        for rec in opens:
            f.write(json.dumps(rec, default=str) + "\n")

    nets = sorted(o.get("net_after") or 0 for o in opens)
    lives = sorted(o["time_open"] for o in opens if o.get("time_open") is not None)
    sizes = Counter(o.get("size") for o in opens)
    routes = Counter(o.get("route") for o in opens)
    kinds = Counter(o.get("kind") for o in opens)
    pools_c = Counter(o.get("pool") for o in opens)
    follow = Counter(o.get("follow") for o in opens)
    fee_moved = sum(1 for x in fired if x.get("fee_delta"))
    surv = len(fired)

    def pct(xs, p):
        if not xs:
            return None
        return xs[min(len(xs) - 1, int(p * (len(xs) - 1)))]

    hours = ((t1 or 0) - (t0 or 0)) / 3600 if t0 and t1 else 0
    theoretical = sum(max(0, n) for n in nets)
    summary = {
        "source": str(RECON),
        "t0": t0,
        "t1": t1,
        "hours": hours,
        "auth": n_auth,
        "scheduled": n_sched,
        "fired_survived": surv,
        "fee_moved": fee_moved,
        "routes_crossing": len(opens),
        "theoretical_net_lamports": theoretical,
        "theoretical_net_sol": theoretical / 1e9,
        "net_p50": pct(nets, 0.5),
        "net_p90": pct(nets, 0.9),
        "net_max": nets[-1] if nets else None,
        "lifetime_p50_s": pct(lives, 0.5),
        "lifetime_p90_s": pct(lives, 0.9),
        "lifetime_max_s": lives[-1] if lives else None,
        "sizes": dict(sizes),
        "routes": dict(routes),
        "open_kinds": dict(kinds),
        "follow": dict(follow),
        "top_pools": pools_c.most_common(15),
        "elapsed_s": time.time() - t_run,
        "no_account_event": sum(1 for o in opens if not o.get("event_at_cross")),
    }
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
