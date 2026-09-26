#!/usr/bin/env python3
"""Refetch the reference MEV.live hour and persist EVERY DLMM/Pump winner.

The existing mev_hour.json only kept top-25 + slot list. The live-hour
funnel needs sig + slot + $ for all 2464.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
sys.path.insert(0, str(ROOT / "arb-cap" / "regress"))
import mev_hour as mh  # noqa: E402

OUT = Path(__file__).resolve().parent / "hour_arbs.jsonl"
META = Path(__file__).resolve().parent / "hour_arbs_meta.json"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    src = json.loads((ROOT / "arb-cap" / "regress" / "mev_hour.json").read_text(encoding="utf-8"))
    t0, t1 = int(src["t0"]), int(src["t1"])
    pending = [(t0, t1)]
    leaves = []
    calls = 0
    while pending:
        batch = pending[:8]
        pending = pending[8:]
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(mh.fetch, a, b): (a, b) for a, b in batch}
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
        print(f"calls={calls} pending={len(pending)} leaves={len(leaves)}", flush=True)

    seen = set()
    rows = []
    usd = 0.0
    for chunk in leaves:
        for r in chunk:
            sig = r.get("signature")
            if not sig or sig in seen:
                continue
            if mh.family(r.get("dexes") or []) != "dlmm_pump":
                continue
            seen.add(sig)
            u = float(r.get("pure_profit") or 0)
            usd += u
            rows.append({
                "sig": sig,
                "slot": int(r["slot"]) if r.get("slot") else None,
                "usd": u,
                "user": r.get("user"),
                "dexes": r.get("dexes"),
                "hops": r.get("number_of_swap_steps"),
                "time": r.get("time"),
            })
    rows.sort(key=lambda x: -x["usd"])
    OUT.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
    META.write_text(json.dumps({
        "t0": t0, "t1": t1, "n": len(rows), "usd": usd, "calls": calls,
        "slots": len({r["slot"] for r in rows if r.get("slot")}),
    }, indent=2), encoding="utf-8")
    print(f"wrote {OUT} n={len(rows)} usd={usd:.2f} slots={META}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
