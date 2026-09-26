#!/usr/bin/env python3
"""Aggregate MEV.live successful arbs over the last hour. No send."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://mev.live/api/arb-explorer/search"
HEADERS = {
    "Referer": "https://mev.live/arbitrages",
    "Origin": "https://mev.live",
    "User-Agent": "arb-off/regress",
}


def fetch(t0: int, t1: int) -> dict:
    q = urllib.parse.urlencode({
        "sort_by": "time",
        "sort_dir": "desc",
        "time_from": t0,
        "time_to": t1,
        "recent_mint_window_secs": 0,
    })
    req = urllib.request.Request(f"{BASE}?{q}", headers=HEADERS)
    last = None
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            time.sleep(0.4 * (i + 1))
    raise RuntimeError(str(last))


def family(dexes: list[str]) -> str:
    s = set(dexes or [])
    if "Meteora DLMM" in s and "Pump Swap" in s and s <= {"Meteora DLMM", "Pump Swap"}:
        return "dlmm_pump"
    if s == {"Meteora DLMM"}:
        return "dlmm_dlmm"
    return "other"


def main() -> int:
    now = int(sys.argv[1]) if len(sys.argv) > 1 else int(time.time())
    t0 = int(sys.argv[2]) if len(sys.argv) > 2 else now - 3600
    pending = [(t0, now)]
    leaves = []
    calls = 0
    while pending:
        batch = pending[:8]
        pending = pending[8:]
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(fetch, a, b): (a, b) for a, b in batch}
            for fut in as_completed(futs):
                a, b = futs[fut]
                resp = fut.result()
                calls += 1
                rows = resp.get("rows") or []
                total = int(resp.get("total_count") or 0)
                if total == 0:
                    continue
                if len(rows) >= total or (b - a) <= 2:
                    leaves.append(rows)
                    continue
                mid = (a + b) // 2
                if mid <= a or mid >= b:
                    leaves.append(rows)
                    continue
                pending.append((a, mid))
                pending.append((mid, b))
        print(f"calls={calls} pending={len(pending)} leaves={len(leaves)}", file=sys.stderr, flush=True)

    seen = set()
    agg = {
        "all": {"n": 0, "usd": 0.0},
        "dlmm_pump": {"n": 0, "usd": 0.0},
        "dlmm_dlmm": {"n": 0, "usd": 0.0},
        "dlmm_pump_2hop": {"n": 0, "usd": 0.0},
    }
    slots = {"dlmm_pump": set(), "dlmm_dlmm": set(), "all": set()}
    top = []
    for rows in leaves:
        for r in rows:
            sig = r.get("signature")
            if not sig or sig in seen:
                continue
            seen.add(sig)
            usd = float(r.get("pure_profit") or 0)
            fam = family(r.get("dexes") or [])
            agg["all"]["n"] += 1
            agg["all"]["usd"] += usd
            if r.get("slot"):
                slots["all"].add(int(r["slot"]))
            if fam == "other":
                continue
            agg[fam]["n"] += 1
            agg[fam]["usd"] += usd
            if r.get("slot"):
                slots[fam].add(int(r["slot"]))
            if fam == "dlmm_pump" and int(r.get("number_of_swap_steps") or 0) == 2:
                agg["dlmm_pump_2hop"]["n"] += 1
                agg["dlmm_pump_2hop"]["usd"] += usd
            if fam == "dlmm_pump":
                top.append({
                    "sig": sig,
                    "slot": r.get("slot"),
                    "usd": usd,
                    "user": r.get("user"),
                    "dexes": r.get("dexes"),
                    "hops": r.get("number_of_swap_steps"),
                    "time": r.get("time"),
                })
    top.sort(key=lambda x: -x["usd"])
    doc = {
        "t0": t0,
        "t1": now,
        "calls": calls,
        "agg": agg,
        "slots": {k: len(v) for k, v in slots.items()},
        "top_dlmm_pump": top[:25],
        "dlmm_pump_slots": sorted(slots["dlmm_pump"]),
    }
    Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\regress\mev_hour.json").write_text(
        json.dumps(doc), encoding="utf-8"
    )
    print(json.dumps({k: doc[k] for k in ("t0", "t1", "calls", "agg", "slots")}, indent=2))
    print("TOP")
    for r in top[:15]:
        print(f"  ${r['usd']:.2f}  slot={r['slot']}  hops={r['hops']}  {r['user'][:8]}  {r['dexes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
