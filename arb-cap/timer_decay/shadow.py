#!/usr/bin/env python3
"""Prospective timer-trigger shadow on live STATE-010 authpub.

Read-only. Does not write shm, does not send, does not touch paper_orbit.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

from auth_ro import latest, n_pools, open_ro, parse_dlmm, parse_pump, PROTO_DLMM, PROTO_PUMP
from dlmm_quote import (
    cycle_quote,
    fee_after_time,
    hurdle,
    next_boundaries,
)

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
OUT = Path(os.environ.get("TIMER_OUT", "/tmp/timer_decay"))
UNIV = Path(os.environ.get("LIVEUNIV", "/home/louis/captures/paper_orbit/liveuniv.json"))
DURATION = float(os.environ.get("TIMER_SECS", "720"))


def load_univ(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return doc["pools"] if isinstance(doc, dict) else doc


def partners(pools: list[dict], dlmm_idx: int) -> list[dict]:
    d = pools[dlmm_idx]
    token = d.get("token") or d.get("mx")
    out = []
    for p in pools:
        if p.get("proto") != "pump":
            continue
        if (p.get("token") or p.get("mx")) == token and (p.get("my") == WSOL or True):
            if d.get("my") == WSOL:
                out.append(p)
    return out


def snapshot_pool(mm, idx: int) -> dict | None:
    row = latest(mm, idx)
    if row is None:
        return None
    if row["proto"] == PROTO_DLMM:
        st = parse_dlmm(row["blob"])
        if st is None:
            return None
        row["dlmm"] = st
    elif row["proto"] == PROTO_PUMP:
        st = parse_pump(row["blob"])
        if st is None:
            return None
        row["pump"] = st
    else:
        return None
    return row


def eval_routes(dlmm, pumps: list[tuple[dict, object]], now_ts: int) -> list[dict]:
    rows = []
    for meta, pump in pumps:
        for direction in (0, 1):
            h = hurdle(direction)
            best = None
            by_size = []
            for lab, ain in zip(SIZE_LABEL, SIZES):
                out = cycle_quote(dlmm, pump, ain, direction, now_ts)
                if out is None:
                    by_size.append({"size": lab, "ain": ain, "aout": None, "gross": None, "net": None})
                    continue
                gross = int(out) - ain
                net = gross - h
                rec = {"size": lab, "ain": ain, "aout": out, "gross": gross, "net": net}
                by_size.append(rec)
                if best is None or net > best["net"]:
                    best = rec
            rows.append({
                "pump": meta.get("pubkey"),
                "pump_idx": meta.get("idx"),
                "route": "dlmm-pump" if direction == 0 else "pump-dlmm",
                "direction": direction,
                "hurdle": h,
                "best": best,
                "sizes": by_size,
            })
    return rows


def mev_window(t0: float, t1: float) -> list[dict]:
    rows = []
    t = t0
    while t < t1:
        w1 = min(t + 8.0, t1)
        body = json.dumps({
            "sort_by": "time", "sort_dir": "asc",
            "time_from": int(t), "time_to": int(w1),
            "recent_mint_window_secs": 0, "page_size": 100,
        }).encode()
        req = urllib.request.Request(
            MEV, data=body, headers={"content-type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                doc = json.loads(r.read().decode())
        except Exception:
            t = w1
            continue
        for row in doc.get("rows") or []:
            rows.append(row)
        t = w1
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    pools = load_univ(UNIV)
    mm = open_ro()
    n = n_pools(mm)
    print(f"auth n_pools={n} univ={len(pools)} duration={DURATION}s out={OUT}", flush=True)

    scheduled: dict[tuple, dict] = {}
    fired: list[dict] = []
    opens: list[dict] = []
    pending_follow: list[dict] = []
    seen_sched = 0
    t_end = time.time() + DURATION
    last_report = 0.0

    while time.time() < t_end:
        now = int(time.time())
        snaps = {}
        for i in range(min(n, len(pools))):
            s = snapshot_pool(mm, i)
            if s:
                snaps[i] = s

        for i, s in snaps.items():
            if s.get("proto") != PROTO_DLMM or "dlmm" not in s:
                continue
            d = s["dlmm"]
            parts = []
            for meta in partners(pools, i):
                ps = snaps.get(meta["idx"])
                if ps and "pump" in ps:
                    parts.append((meta, ps["pump"], ps["generation"], ps["idx"]))
            if not parts:
                continue
            for kind, ts in next_boundaries(d, now):
                key = (i, s["generation"], kind, ts)
                if key in scheduled:
                    continue
                pumps = [(m, p) for m, p, _, _ in parts]
                econ0 = eval_routes(d, pumps, now)
                fee0, vacc0, vref0 = fee_after_time(d, now)
                scheduled[key] = {
                    "pool": pools[i]["pubkey"],
                    "pool_idx": i,
                    "token": pools[i].get("token"),
                    "scheduled_at": now,
                    "decay_boundary": ts,
                    "kind": kind,
                    "gen": s["generation"],
                    "slot": s["slot"],
                    "pump_gens": {idx: gen for _, _, gen, idx in parts},
                    "dlmm": d,
                    "pumps": parts,
                    "econ0": econ0,
                    "fee_before": fee0,
                    "vol_acc_before": vacc0,
                    "vol_ref_before": vref0,
                    "last_upd": d.last_upd,
                    "filter_period": d.filter_period,
                    "decay_period": d.decay_period,
                    "reduction_factor": d.reduction_factor,
                    "vfc": d.variable_fee_control,
                    "vol_acc_stored": d.vol_acc,
                }
                seen_sched += 1

        due = [k for k, v in scheduled.items() if now >= v["decay_boundary"] and not v.get("fired")]
        for key in due:
            job = scheduled[key]
            job["fired"] = True
            cur = snaps.get(job["pool_idx"])
            survived = bool(
                cur and cur.get("generation") == job["gen"] and "dlmm" in cur
            )
            pump_ok = True
            if survived:
                for _, _, gen, idx in job["pumps"]:
                    ps = snaps.get(idx)
                    if not ps or ps.get("generation") != gen:
                        pump_ok = False
                        break
            fee1, vacc1, vref1 = fee_after_time(job["dlmm"], job["decay_boundary"])
            econ1 = eval_routes(job["dlmm"], [(m, p) for m, p, _, _ in job["pumps"]], job["decay_boundary"])
            crosses = []
            if survived:
                by0 = {(r["pump_idx"], r["direction"]): r for r in job["econ0"]}
                for r1 in econ1:
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
            rec = {
                "pool": job["pool"],
                "pool_idx": job["pool_idx"],
                "token": job["token"],
                "route": None,
                "scheduled_at": job["scheduled_at"],
                "decay_boundary": job["decay_boundary"],
                "kind": job["kind"],
                "survived_to_boundary": survived,
                "partner_untouched": survived and pump_ok,
                "event_at_cross": (not survived),
                "fee_before": job["fee_before"],
                "fee_after": fee1,
                "vol_acc_before": job["vol_acc_before"],
                "vol_acc_after": vacc1,
                "vol_ref_before": job["vol_ref_before"],
                "vol_ref_after": vref1,
                "fee_delta": fee1 - job["fee_before"],
                "crosses": crosses,
                "crossed_hurdle": bool(crosses),
                "econ1": econ1,
                "slot_at_sched": job["slot"],
                "gen": job["gen"],
                "fired_at": now,
            }
            if crosses:
                best = max(crosses, key=lambda x: x["net_after"])
                rec["route"] = best["route"]
                rec["size"] = best["size"]
                rec["net_before"] = best["net_before"]
                rec["net_after"] = best["net_after"]
                rec["gross_before"] = best["gross_before"]
                rec["gross_after"] = best["gross_after"]
                rec["subsequent_taker"] = None
                rec["known_searcher"] = None
                rec["time_open"] = None
                rec["follow"] = "WATCH"
                pending_follow.append(rec)
                opens.append(rec)
            fired.append(rec)

        still = []
        for rec in pending_follow:
            cur = snaps.get(rec["pool_idx"])
            if cur and cur.get("generation") != rec["gen"]:
                rec["time_open"] = int(time.time()) - rec["decay_boundary"]
                rec["closed_slot"] = cur.get("slot")
                rec["follow"] = "NATURALLY_CLOSED_BY_FLOW"
                rec["close_sig"] = cur.get("sig").hex() if cur.get("sig") else None
            elif time.time() >= t_end - 0.5:
                rec["time_open"] = int(time.time()) - rec["decay_boundary"]
                rec["follow"] = "STILL_OPEN"
            else:
                still.append(rec)
        pending_follow = still

        if time.time() - last_report > 15:
            last_report = time.time()
            print(
                f"t+{int(DURATION - (t_end - time.time()))}s sched={len(scheduled)} "
                f"fired={len(fired)} survived={sum(1 for x in fired if x['survived_to_boundary'])} "
                f"cross={len(opens)}",
                flush=True,
            )
        time.sleep(0.05)

    for rec in pending_follow:
        rec["time_open"] = int(time.time()) - rec["decay_boundary"]
        rec["follow"] = "STILL_OPEN"

    # MEV control on openings only
    if opens:
        t0 = min(o["decay_boundary"] for o in opens) - 2
        t1 = max(o.get("fired_at") or o["decay_boundary"] for o in opens) + 8
        arbs = mev_window(float(t0), float(t1) + 30)
        by_mint = defaultdict(list)
        for a in arbs:
            if a.get("two_leg_arb_mint"):
                by_mint[a["two_leg_arb_mint"]].append(a)
        for rec in opens:
            hits = []
            for a in by_mint.get(rec.get("token") or "", []):
                if rec["decay_boundary"] <= int(a.get("time") or 0) <= rec["decay_boundary"] + 30:
                    hits.append(a)
            if hits:
                rec["subsequent_taker"] = hits[0].get("signature")
                rec["known_searcher"] = SEARCHERS.get(hits[0].get("user") or "", hits[0].get("user"))
                if rec.get("follow") == "STILL_OPEN":
                    rec["follow"] = "CAPTURED_KNOWN_ARB" if rec["known_searcher"] in SEARCHERS.values() else "CAPTURED_UNKNOWN_SEARCHER"
            elif rec.get("follow") == "NATURALLY_CLOSED_BY_FLOW":
                pass
            elif rec.get("follow") == "STILL_OPEN":
                rec["subsequent_taker"] = None

    ledger_path = OUT / "LEDGER.jsonl"
    with ledger_path.open("w", encoding="utf-8") as f:
        for rec in fired:
            slim = {k: rec[k] for k in rec if k not in ("econ1", "dlmm", "pumps")}
            if "econ1" in rec:
                slim["best_after"] = [r.get("best") for r in rec["econ1"]]
            f.write(json.dumps(slim, default=str) + "\n")

    opens_path = OUT / "TIMER_DECAY_OPEN.jsonl"
    with opens_path.open("w", encoding="utf-8") as f:
        for rec in opens:
            slim = {k: rec[k] for k in rec if k not in ("econ1", "dlmm", "pumps")}
            f.write(json.dumps(slim, default=str) + "\n")

    survived = [x for x in fired if x["survived_to_boundary"]]
    partner_ok = [x for x in fired if x.get("partner_untouched")]
    fee_moved = [x for x in survived if x["fee_delta"] != 0]
    lifetimes = [o["time_open"] for o in opens if o.get("time_open") is not None]
    lifetimes.sort()
    theoretical = sum(max(0, o.get("net_after") or 0) for o in opens)

    def pct(xs, p):
        if not xs:
            return None
        return xs[int(p * (len(xs) - 1))]

    summary = {
        "duration_s": DURATION,
        "scheduled": len(scheduled),
        "fired": len(fired),
        "survived_untouched": len(survived),
        "partner_untouched": len(partner_ok),
        "fee_moved": len(fee_moved),
        "routes_crossing": len(opens),
        "theoretical_net_opened_lamports": theoretical,
        "theoretical_net_opened_sol": theoretical / 1e9,
        "lifetime_median_s": pct(lifetimes, 0.5),
        "lifetime_p90_s": pct(lifetimes, 0.9),
        "follow": {
            "captured_known": sum(1 for o in opens if o.get("follow") == "CAPTURED_KNOWN_ARB"),
            "captured_unknown": sum(1 for o in opens if o.get("follow") == "CAPTURED_UNKNOWN_SEARCHER"),
            "naturally_closed": sum(1 for o in opens if o.get("follow") == "NATURALLY_CLOSED_BY_FLOW"),
            "still_open": sum(1 for o in opens if o.get("follow") == "STILL_OPEN"),
        },
        "kinds": {
            "filter": sum(1 for x in fired if x["kind"] == "filter"),
            "decay": sum(1 for x in fired if x["kind"] == "decay"),
        },
        "no_account_event_crosses": sum(1 for o in opens if not o.get("event_at_cross")),
    }
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
