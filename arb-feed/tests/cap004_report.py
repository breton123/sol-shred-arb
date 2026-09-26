#!/usr/bin/env python3
"""CAP-004 tables from hits.jsonl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

LOCAL_US = 20.0


def pct(xs, p):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    xs = sorted(xs)
    i = int(round((p / 100.0) * (len(xs) - 1)))
    return xs[max(0, min(i, len(xs) - 1))]


def fmt(v):
    if v is None:
        return "—"
    return f"{v:.1f}"


def classify(h):
    if not h.get("mriya_found") or not h.get("trig_found"):
        return None
    ms, ts = h["mriya_shred0"], h["trig_shred0"]
    mf, tf = h["mriya_fec0"], h["trig_fec0"]
    dsh = int(ms) - int(ts)
    dfec = 0 if mf == tf else 1
    if ms == ts:
        kind = "same_shred"
    elif dsh == 1:
        kind = "next_shred"
    elif mf == tf:
        kind = "same_fec"
    else:
        kind = "diff_fec"
    return {
        "kind": kind,
        "d_shred": dsh,
        "d_fec": (int(mf) - int(tf)) if mf is not None else None,
        "same_fec": mf == tf,
    }


def dt_us(later, earlier):
    if later is None or earlier is None or later == 0 or earlier == 0:
        return None
    return (int(later) - int(earlier)) / 1000.0


def table(title, both):
    kinds = {"same_shred": 0, "next_shred": 0, "same_fec": 0, "diff_fec": 0}
    n_first, n_act, n_comp, budget = [], [], [], []
    for r in both:
        c = classify(r)
        if c:
            kinds[c["kind"]] += 1
        mf = r.get("mriya_rx0")
        n_first.append(dt_us(mf, r.get("trig_rx0")))
        n_act.append(dt_us(mf, r.get("act_rx") if r.get("act_found") else None))
        n_comp.append(dt_us(mf, r.get("trig_rx1")))
        a = dt_us(mf, r.get("act_rx") if r.get("act_found") else None)
        if a is not None:
            budget.append(a - LOCAL_US)
    n = len(both)
    print(title)
    print()
    print(f"matched immediate races       {n}")
    print()
    print("physical serialization         n     Share")
    for k, label in (
        ("same_shred", "same shred"),
        ("next_shred", "next shred"),
        ("same_fec", "same FEC"),
        ("diff_fec", "different FEC"),
    ):
        v = kinds[k]
        share = 100.0 * v / n if n else 0
        print(f"  {label:<24} {v:>5}  {share:5.1f}%")
    print()
    print("Available window (us)         p10       p50       p90       p99")

    def row(name, xs):
        print(
            f"{name:<28} {fmt(pct(xs,10)):>8} {fmt(pct(xs,50)):>8} {fmt(pct(xs,90)):>8} {fmt(pct(xs,99)):>8}"
        )

    row("N first -> Mriya first", n_first)
    row("N actionable -> Mriya first", n_act)
    row("N complete -> Mriya first", n_comp)
    print()
    print(f"our local (signed ready)      {LOCAL_US:.1f} us")
    row("budget_return (act-20us)", budget)
    neg = sum(1 for b in budget if b is not None and b < 0)
    print(f"budget_return < 0             {neg}/{len(budget)}")
    print()
    return n


def main():
    hits = Path(sys.argv[1])
    pairs_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    rows = [json.loads(l) for l in hits.read_text(encoding="utf-8").splitlines() if l.strip()]
    dex = {}
    if pairs_path and pairs_path.exists():
        for line in pairs_path.read_text(encoding="utf-8").splitlines():
            p = json.loads(line)
            dex[p.get("mriya_sig")] = tuple(p.get("dexes") or [])
    imm = [r for r in rows if r.get("immediate") and r.get("pair_ok")]
    both = [r for r in imm if r.get("mriya_found") and r.get("trig_found")]
    kinds = {"same_shred": 0, "next_shred": 0, "same_fec": 0, "diff_fec": 0}
    n_first, n_act, n_comp, budget = [], [], [], []
    for r in both:
        c = classify(r)
        if c:
            kinds[c["kind"]] += 1
        mf = r.get("mriya_rx0")
        n_first.append(dt_us(mf, r.get("trig_rx0")))
        n_act.append(dt_us(mf, r.get("act_rx") if r.get("act_found") else None))
        n_comp.append(dt_us(mf, r.get("trig_rx1")))
        a = dt_us(mf, r.get("act_rx") if r.get("act_found") else None)
        if a is not None:
            budget.append(a - LOCAL_US)

    n = len(both)
    print("CAP-004  MRIYA N+1 — PREMIUM SHRED FEED")
    print()
    print(f"pairs in file                 {len(rows)}")
    print(f"immediate (dist<=2)           {len(imm)}")
    print(f"both located in capture       {n}")
    print(f"mriya found                   {sum(1 for r in rows if r.get('mriya_found'))}")
    print(f"trigger found                 {sum(1 for r in rows if r.get('trig_found'))}")
    print()
    print("Mriya immediate races          n     Share")
    for k, label in (
        ("same_shred", "Trigger + Mriya overlap same shred"),
        ("next_shred", "Mriya next shred"),
        ("same_fec", "Same FEC (not same/next shred)"),
        ("diff_fec", "Different FEC"),
    ):
        v = kinds[k]
        share = 100.0 * v / n if n else 0
        print(f"{label:<36} {v:>5}  {share:5.1f}%")
    print()
    print("Available window (µs)         p10       p50       p90       p99")

    def row(name, xs):
        print(
            f"{name:<28} {fmt(pct(xs,10)):>8} {fmt(pct(xs,50)):>8} {fmt(pct(xs,90)):>8} {fmt(pct(xs,99)):>8}"
        )

    row("N first -> Mriya first", n_first)
    row("N actionable -> Mriya first", n_act)
    row("N complete -> Mriya first", n_comp)
    print()
    print(f"our local (signed ready)      {LOCAL_US:.1f} us")
    row("budget_return (act-20us)", budget)
    neg = sum(1 for b in budget if b is not None and b < 0)
    print(f"budget_return < 0             {neg}/{len(budget)}")
    print()
    dlmm_pump = [
        r
        for r in both
        if dex.get(r.get("mriya_sig")) == ("Meteora DLMM", "Pump Swap")
    ]
    if dlmm_pump:
        table("DLMM -> Pump immediate only", dlmm_pump)


if __name__ == "__main__":
    main()
