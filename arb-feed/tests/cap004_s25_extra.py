#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

HITS = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004_s25\cap004_hits.jsonl")
PAIRS = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004_s25\pairs.jsonl")
MRIYA_H = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004\cap004_hits.jsonl")
MRIYA_P = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004\pairs.jsonl")
LOCAL = 20.0

SHORT = {
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


def dt_us(later, earlier):
    if later is None or earlier is None or later == 0 or earlier == 0:
        return None
    return (int(later) - int(earlier)) / 1000.0


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
        r["dist"] = r.get("dist") if r.get("dist") is not None else p.get("dist")
        rows.append(r)
    return rows, meta


def bucket(d):
    if d is None:
        return "na"
    d = int(d)
    if d <= 2:
        return "imm<=2"
    if d <= 5:
        return "3-5"
    if d <= 20:
        return "6-20"
    return "21+"


def stats(rows):
    both = [r for r in rows if r.get("mriya_found") and r.get("trig_found")]
    acts, buds, prof_pos, prof_all = [], [], 0.0, 0.0
    pos = neg = act0 = 0
    for r in both:
        a = dt_us(r.get("mriya_rx0"), r.get("act_rx") if r.get("act_found") else None)
        acts.append(a)
        if a is None:
            continue
        b = a - LOCAL
        buds.append(b)
        prof_all += r.get("profit") or 0
        if a == 0:
            act0 += 1
        if b >= 0:
            pos += 1
            prof_pos += r.get("profit") or 0
        else:
            neg += 1
    return {
        "n": len(both),
        "act0": act0,
        "pos": pos,
        "neg": neg,
        "p50": pct(acts, 50),
        "p90": pct(acts, 90),
        "p99": pct(acts, 99),
        "bp50": pct(buds, 50),
        "bp90": pct(buds, 90),
        "profit_pos": prof_pos,
        "profit_all": prof_all,
    }


rows, meta = load(HITS, PAIRS)
print("pairs file", len(meta), "hits", len(rows))
print()
print("PAIR FILE (before locate)")
print(f"{'who':<8} {'n':>5} {'ok':>5} {'imm':>5} {'imm%':>6} {'profit':>10}")
by = defaultdict(list)
for p in meta.values():
    by[p.get("user")].append(p)
for u, short in SHORT.items():
    ps = by[u]
    ok = sum(1 for p in ps if p.get("pair_ok"))
    imm = sum(1 for p in ps if p.get("immediate"))
    pr = sum(float(p.get("profit") or 0) for p in ps)
    print(f"{short:<8} {len(ps):5} {ok:5} {imm:5} {100*imm/len(ps) if ps else 0:5.1f}% {pr:10.1f}")

print()
print("LOCATED  N-actionable -> searcher  (all distances)")
print(f"{'who':<8} {'n':>5} {'act=0':>6} {'bud>=0':>7} {'p50':>8} {'p90':>8} {'p99':>8} {'$>=0':>10} {'$all':>10}")
order = list(SHORT.items())
for u, short in order:
    st = stats([r for r in rows if r.get("user") == u])
    print(
        f"{short:<8} {st['n']:5} {st['act0']:6} {st['pos']:7} "
        f"{fmt(st['p50']):>8} {fmt(st['p90']):>8} {fmt(st['p99']):>8} "
        f"{st['profit_pos']:10.1f} {st['profit_all']:10.1f}"
    )
st = stats(rows)
print(
    f"{'ALL':<8} {st['n']:5} {st['act0']:6} {st['pos']:7} "
    f"{fmt(st['p50']):>8} {fmt(st['p90']):>8} {fmt(st['p99']):>8} "
    f"{st['profit_pos']:10.1f} {st['profit_all']:10.1f}"
)

print()
print("BY DISTANCE  (pooled 5 searchers)")
print(f"{'dist':<8} {'n':>5} {'act=0':>6} {'bud>=0':>7} {'p50 act':>8} {'p90 act':>8} {'$>=0':>10}")
for bname in ("imm<=2", "3-5", "6-20", "21+"):
    sub = [r for r in rows if bucket(r.get("dist")) == bname]
    st = stats(sub)
    print(
        f"{bname:<8} {st['n']:5} {st['act0']:6} {st['pos']:7} "
        f"{fmt(st['p50']):>8} {fmt(st['p90']):>8} {st['profit_pos']:10.1f}"
    )

print()
print("BY DISTANCE x SEARCHER  bud>=0 / n")
print(f"{'who':<8} {'imm':>12} {'3-5':>12} {'6-20':>12} {'21+':>12}")
for u, short in order:
    cells = []
    for bname in ("imm<=2", "3-5", "6-20", "21+"):
        sub = [r for r in rows if r.get("user") == u and bucket(r.get("dist")) == bname]
        st = stats(sub)
        cells.append(f"{st['pos']}/{st['n']}")
    print(f"{short:<8} " + " ".join(f"{c:>12}" for c in cells))

print()
print("POSITIVE-BUDGET races: profit + act window")
pos_rows = []
for r in rows:
    if not (r.get("mriya_found") and r.get("trig_found") and r.get("act_found")):
        continue
    a = dt_us(r.get("mriya_rx0"), r.get("act_rx"))
    if a is None or a < LOCAL:
        continue
    pos_rows.append((a, r.get("profit") or 0, r.get("user"), r.get("dist"), r.get("dexes")))
pos_rows.sort(reverse=True)
print(f"n={len(pos_rows)} profit_sum={sum(p for _,p,_,_,_ in pos_rows):.1f}")
print(f"{'act_us':>10} {'profit':>10} {'dist':>6} {'who':<8} dexes")
for a, pr, u, d, dex in pos_rows[:25]:
    print(f"{a:10.1f} {pr:10.3f} {str(d):>6} {SHORT.get(u,'?'):<8} {dex}")

print()
print("MRIYA compare (immediate both-found)")
mh, _ = load(MRIYA_H, MRIYA_P, "Mriya")
imm_m = [r for r in mh if r.get("immediate") and r.get("pair_ok")]
st = stats(imm_m)
print(
    f"Mriya imm n={st['n']} act0={st['act0']} bud>=0={st['pos']} "
    f"p50={fmt(st['p50'])} p90={fmt(st['p90'])} $pos={st['profit_pos']:.1f}"
)
