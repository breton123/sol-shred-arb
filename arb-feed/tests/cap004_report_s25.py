#!/usr/bin/env python3
"""CAP-004 tables per searcher from hits + pairs."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

LOCAL_US = 20.0

SHORT = {
    "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X": "Mriya",
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "Dtvmxr",
    "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu": "7dGrdJ",
    "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK": "4BQ6AT",
    "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd": "gtagyE",
    "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4": "9EwQoN",
}


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
    if ms == ts:
        kind = "same_shred"
    elif dsh == 1:
        kind = "next_shred"
    elif mf == tf:
        kind = "same_fec"
    else:
        kind = "diff_fec"
    return {"kind": kind, "d_shred": dsh, "same_fec": mf == tf}


def dt_us(later, earlier):
    if later is None or earlier is None or later == 0 or earlier == 0:
        return None
    return (int(later) - int(earlier)) / 1000.0


def table(title, both, label):
    kinds = {"same_shred": 0, "next_shred": 0, "same_fec": 0, "diff_fec": 0}
    n_first, n_act, n_comp, budget = [], [], [], []
    act_gt20 = act_gt1ms = act0 = 0
    for r in both:
        c = classify(r)
        if c:
            kinds[c["kind"]] += 1
        mf = r.get("mriya_rx0")
        n_first.append(dt_us(mf, r.get("trig_rx0")))
        a = dt_us(mf, r.get("act_rx") if r.get("act_found") else None)
        n_act.append(a)
        n_comp.append(dt_us(mf, r.get("trig_rx1")))
        if a is not None:
            budget.append(a - LOCAL_US)
            if a == 0:
                act0 += 1
            if a > 20:
                act_gt20 += 1
            if a > 1000:
                act_gt1ms += 1
    n = len(both)
    print(title)
    print()
    print(f"matched immediate races       {n}")
    print()
    print("physical serialization         n     Share")
    for k, lab in (
        ("same_shred", "same shred"),
        ("next_shred", "next shred"),
        ("same_fec", "same FEC"),
        ("diff_fec", "different FEC"),
    ):
        v = kinds[k]
        share = 100.0 * v / n if n else 0
        print(f"  {lab:<24} {v:>5}  {share:5.1f}%")
    print()
    print("Available window (us)         p10       p50       p90       p99")

    def row(name, xs):
        print(
            f"{name:<28} {fmt(pct(xs,10)):>8} {fmt(pct(xs,50)):>8} {fmt(pct(xs,90)):>8} {fmt(pct(xs,99)):>8}"
        )

    row(f"N first -> {label} first", n_first)
    row(f"N actionable -> {label} first", n_act)
    row(f"N complete -> {label} first", n_comp)
    print()
    print(f"our local (signed ready)      {LOCAL_US:.1f} us")
    row("budget_return (act-20us)", budget)
    neg = sum(1 for b in budget if b is not None and b < 0)
    pos = sum(1 for b in budget if b is not None and b >= 0)
    print(f"budget_return < 0             {neg}/{len(budget)}")
    print(f"budget_return >= 0            {pos}/{len(budget)}")
    print(f"act == 0                      {act0}/{len(budget)}")
    print(f"act > 20us                    {act_gt20}/{len(budget)}")
    print(f"act > 1ms                     {act_gt1ms}/{len(budget)}")
    print()
    return {
        "n": n,
        "kinds": kinds,
        "n_first": n_first,
        "n_act": n_act,
        "budget": budget,
        "neg": neg,
        "pos": pos,
        "act0": act0,
        "act_gt20": act_gt20,
        "act_gt1ms": act_gt1ms,
    }


def main():
    hits_path = Path(sys.argv[1])
    pairs_path = Path(sys.argv[2])
    rows = [json.loads(l) for l in hits_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    meta = {}
    for line in pairs_path.read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        meta[p.get("mriya_sig")] = p
    for r in rows:
        p = meta.get(r.get("mriya_sig")) or {}
        r["user"] = p.get("user")
        r["dexes"] = tuple(p.get("dexes") or [])
        r["profit"] = p.get("profit")

    print("CAP-004  TOP-5 AFTER MRIYA — PREMIUM SHRED FEED")
    print()
    print(f"pairs in hits                 {len(rows)}")
    print(f"immediate (dist<=2)           {sum(1 for r in rows if r.get('immediate') and r.get('pair_ok'))}")
    print(f"searcher found                {sum(1 for r in rows if r.get('mriya_found'))}")
    print(f"trigger found                 {sum(1 for r in rows if r.get('trig_found'))}")
    print()

    order = [
        "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx",
        "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu",
        "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK",
        "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd",
        "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4",
    ]
    summary = []
    for u in order:
        label = SHORT.get(u, u[:8])
        subset = [
            r
            for r in rows
            if r.get("user") == u
            and r.get("immediate")
            and r.get("pair_ok")
            and r.get("mriya_found")
            and r.get("trig_found")
        ]
        st = table(f"=== {label}  {u} ===", subset, label)
        dp = [r for r in subset if r.get("dexes") == ("Meteora DLMM", "Pump Swap")]
        if dp:
            table(f"DLMM -> Pump immediate only  ({label})", dp, label)
        summary.append((label, u, st))

    all_both = [
        r
        for r in rows
        if r.get("immediate")
        and r.get("pair_ok")
        and r.get("mriya_found")
        and r.get("trig_found")
    ]
    table("=== ALL FIVE (pooled) ===", all_both, "searcher")

    print("SUMMARY  budget_return vs 20us local")
    print(f"{'who':<10} {'imm':>6} {'bud<0':>8} {'bud>=0':>8} {'act=0':>7} {'act>20':>8} {'p50 act':>8} {'p90 act':>8}")
    for label, u, st in summary:
        print(
            f"{label:<10} {st['n']:6} {st['neg']:8} {st['pos']:8} {st['act0']:7} "
            f"{st['act_gt20']:8} {fmt(pct(st['n_act'],50)):>8} {fmt(pct(st['n_act'],90)):>8}"
        )


if __name__ == "__main__":
    main()
