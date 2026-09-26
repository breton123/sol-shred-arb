#!/usr/bin/env python3
"""439 no-Mriya +budget races: profit × window × protocol, then late-book paper replay."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
S25H = ROOT / "arb-cap" / "cap004_s25" / "cap004_hits.jsonl"
S25P = ROOT / "arb-cap" / "cap004_s25" / "pairs.jsonl"
MH = ROOT / "arb-cap" / "cap004" / "cap004_hits.jsonl"
MP = ROOT / "arb-cap" / "cap004" / "pairs.jsonl"
OUT = ROOT / "arb-cap" / "cap005_late"
LOCAL = 20.0
SUPPORTED = {("Meteora DLMM", "Pump Swap"), ("Pump Swap", "Meteora DLMM")}

PROFIT_BINS = [
    ("<$0.10", 0.0, 0.10),
    ("$0.10–1", 0.10, 1.0),
    ("$1–5", 1.0, 5.0),
    ("$5–10", 5.0, 10.0),
    ("$10–50", 10.0, 50.0),
    ("$50+", 50.0, 1e18),
]
WINDOW_BINS = [
    ("20–50 µs", 20.0, 50.0),
    ("50–100 µs", 50.0, 100.0),
    ("100–250 µs", 100.0, 250.0),
    ("250–500 µs", 250.0, 500.0),
    ("0.5–1 ms", 500.0, 1000.0),
    ("1–5 ms", 1000.0, 5000.0),
    ("5 ms+", 5000.0, 1e18),
]
SHORT = {
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "Dtvmxr",
    "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu": "7dGrdJ",
    "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK": "4BQ6AT",
    "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd": "gtagyE",
    "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4": "9EwQoN",
}


def dt_us(later, earlier):
    if later is None or earlier is None or later == 0 or earlier == 0:
        return None
    return (int(later) - int(earlier)) / 1000.0


def pct(xs, p):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    xs = sorted(xs)
    i = int(round((p / 100.0) * (len(xs) - 1)))
    return xs[max(0, min(i, len(xs) - 1))]


def load(hits_p, pairs_p, default_user=None):
    meta = {}
    for line in pairs_p.read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        meta[p.get("mriya_sig")] = p
    rows = []
    for line in hits_p.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        p = meta.get(r.get("mriya_sig")) or {}
        r["user"] = p.get("user") or default_user
        r["profit"] = float(p.get("profit") or 0)
        r["dexes"] = tuple(p.get("dexes") or [])
        r["hops"] = p.get("hops")
        r["confidence"] = p.get("confidence")
        rows.append(r)
    return rows


def route_name(dexes):
    if not dexes:
        return "(none)"
    return " -> ".join(dexes)


def in_bin(v, lo, hi):
    return v >= lo and v < hi


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    srows = load(S25H, S25P)
    mrows = load(MH, MP, "Mriya")
    mriya_slots = {int(r["slot"]) for r in mrows if r.get("mriya_found")}

    late = []
    for r in srows:
        if not (r.get("mriya_found") and r.get("trig_found") and r.get("act_found")):
            continue
        if int(r["slot"]) in mriya_slots:
            continue
        act = dt_us(r.get("mriya_rx0"), r.get("act_rx"))
        if act is None or act < LOCAL:
            continue
        rec = {
            "sig": r.get("mriya_sig"),
            "trigger_sig": r.get("trigger_sig"),
            "slot": int(r["slot"]),
            "user": r.get("user"),
            "who": SHORT.get(r.get("user"), (r.get("user") or "?")[:8]),
            "profit": r.get("profit") or 0.0,
            "dexes": list(r.get("dexes") or []),
            "route": route_name(r.get("dexes") or ()),
            "hops": r.get("hops"),
            "dist": r.get("dist"),
            "confidence": r.get("confidence"),
            "act_us": act,
            "lead_us": act - LOCAL,
            "supported": tuple(r.get("dexes") or ()) in SUPPORTED,
            "signed_ready_ns": int(r["act_rx"]) + int(LOCAL * 1000),
            "competitor_rx_ns": int(r["mriya_rx0"]),
        }
        late.append(rec)

    late.sort(key=lambda x: -x["profit"])
    (OUT / "races.jsonl").write_text(
        "".join(json.dumps(x, separators=(",", ":")) + "\n" for x in late),
        encoding="utf-8",
    )

    def bucket_rows(rows, bins, key):
        out = []
        for name, lo, hi in bins:
            xs = [r for r in rows if in_bin(r[key], lo, hi)]
            out.append(
                {
                    "bin": name,
                    "n": len(xs),
                    "profit": sum(r["profit"] for r in xs),
                    "supported_n": sum(1 for r in xs if r["supported"]),
                    "supported_profit": sum(r["profit"] for r in xs if r["supported"]),
                }
            )
        return out

    profit_tab = bucket_rows(late, PROFIT_BINS, "profit")
    window_tab = bucket_rows(late, WINDOW_BINS, "act_us")

    routes = Counter()
    route_profit = defaultdict(float)
    route_n = Counter()
    for r in late:
        route_n[r["route"]] += 1
        route_profit[r["route"]] += r["profit"]
    route_tab = [
        {"route": k, "n": route_n[k], "profit": route_profit[k]}
        for k in sorted(route_n, key=lambda k: -route_profit[k])
    ]

    # cross: profit × window for supported only and all
    def cross(rows):
        grid = []
        for pn, plo, phi in PROFIT_BINS:
            for wn, wlo, whi in WINDOW_BINS:
                xs = [r for r in rows if in_bin(r["profit"], plo, phi) and in_bin(r["act_us"], wlo, whi)]
                if not xs:
                    continue
                grid.append(
                    {
                        "profit": pn,
                        "window": wn,
                        "n": len(xs),
                        "profit_sum": sum(r["profit"] for r in xs),
                    }
                )
        return grid

    sweet = [
        r
        for r in late
        if r["supported"] and r["profit"] >= 1.0 and r["act_us"] >= 500.0
    ]
    sweet_loose = [
        r
        for r in late
        if r["supported"] and r["profit"] >= 0.10 and r["act_us"] >= 250.0
    ]
    supported = [r for r in late if r["supported"]]
    leads = [r["lead_us"] for r in supported]

    summary = {
        "eligible": len(late),
        "eligible_profit": sum(r["profit"] for r in late),
        "supported_n": len(supported),
        "supported_profit": sum(r["profit"] for r in supported),
        "core_sees": 0,
        "core_predicted": 0.0,
        "core_why": "no historical DLMM bin snapshot; cycle_size not run",
        "signed_before": len(supported),
        "signed_before_all": len(late),
        "median_lead_supported_us": pct(leads, 50),
        "p10_lead_supported_us": pct(leads, 10),
        "p90_lead_supported_us": pct(leads, 90),
        "sweet_n": len(sweet),
        "sweet_profit": sum(r["profit"] for r in sweet),
        "sweet_loose_n": len(sweet_loose),
        "sweet_loose_profit": sum(r["profit"] for r in sweet_loose),
        "profit_tab": profit_tab,
        "window_tab": window_tab,
        "route_tab": route_tab[:20],
        "cross_all": cross(late),
        "cross_supported": cross(supported),
        "by_who": [
            {
                "who": SHORT[u],
                "n": sum(1 for r in late if r["user"] == u),
                "profit": sum(r["profit"] for r in late if r["user"] == u),
                "supported_n": sum(1 for r in late if r["user"] == u and r["supported"]),
                "supported_profit": sum(r["profit"] for r in late if r["user"] == u and r["supported"]),
            }
            for u in SHORT
            if any(r["user"] == u for r in late)
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = []
    a = lines.append
    a("LATE-BOOK  no-Mriya + budget_return>=0")  # noqa: ASCII report
    a(f"eligible races             {len(late)}")
    a(f"competitor realized        ${sum(r['profit'] for r in late):.1f}")
    a("")
    a("PROFIT")
    a(f"{'bin':<12} {'n':>5} {'$':>10} {'supp n':>7} {'supp $':>10}")
    for row in profit_tab:
        a(f"{row['bin']:<12} {row['n']:5} {row['profit']:10.1f} {row['supported_n']:7} {row['supported_profit']:10.1f}")
    a("")
    a("WINDOW (N-actionable -> competitor first)")
    a(f"{'bin':<12} {'n':>5} {'$':>10} {'supp n':>7} {'supp $':>10}")
    for row in window_tab:
        a(f"{row['bin']:<12} {row['n']:5} {row['profit']:10.1f} {row['supported_n']:7} {row['supported_profit']:10.1f}")
    a("")
    a("PROTOCOL")
    a(f"{'route':<72} {'n':>5} {'$':>10}")
    for row in route_tab[:15]:
        a(f"{row['route']:<72} {row['n']:5} {row['profit']:10.1f}")
    a("")
    a("SWEET SPOT  supported DLMM↔Pump ∩ profit≥$1 ∩ window≥500µs")
    a(f"n={len(sweet)}  ${sum(r['profit'] for r in sweet):.1f}")
    a("loose  supported ∩ ≥$0.10 ∩ ≥250µs")
    a(f"n={len(sweet_loose)}  ${sum(r['profit'] for r in sweet_loose):.1f}")
    a("")
    a("LATE-BOOK PAPER REPLAY")
    a(f"eligible races             {len(late)}")
    a(f"our supported route        {len(supported)}")
    a("our core sees +PnL         0")
    a("our predicted profit       $0")
    a(f"competitor realized        ${sum(r['profit'] for r in late):.1f}")
    a(f"  of which supported       ${sum(r['profit'] for r in supported):.1f}")
    a(f"our signed-ready before competitor:")
    a(f"                           {len(late)} / {len(late)}  (all, by construction)")
    a(f"  on supported only        {len(supported)} / {len(supported)}")
    a(f"median lead (supported)    {pct(leads, 50):.1f} µs" if leads else "median lead                —")
    a(f"p10 / p90 lead             {pct(leads, 10):.1f} / {pct(leads, 90):.1f} µs" if leads else "")
    a("")
    a("CORE: cycle_size not run. Trial window has no DLMM bin snapshots;")
    a("the 80 CORE-004 triples are earlier slots and do not overlap.")
    a("V1 gate that we CAN answer from this corpus is route ∩ window ∩ $.")
    text = "\n".join(lines) + "\n"
    (OUT / "LATE_BOOK.txt").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(text)


if __name__ == "__main__":
    main()
