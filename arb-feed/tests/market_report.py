#!/usr/bin/env python3
"""SHRED_V1_MARKET tables from full-window pairs + cap004 hits."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "arb-cap" / "shred_v1"
HITS = OUT / "hits.jsonl"
PAIRS = OUT / "pairs.jsonl"
MD = OUT / "SHRED_V1_MARKET.md"
HOURS = 11913.749 / 3600.0

MRIYA = "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X"
BQ = "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK"
DTVM = "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx"
ELITE = {MRIYA, BQ, DTVM}
SHORT = {MRIYA: "Mriya", BQ: "4BQ6AT", DTVM: "Dtvmxr"}

BUDGETS = [20, 50, 100, 250, 500, 1000, 2000, 5000, 10000]
BUDGET_COLS = [50, 100, 250, 500, 1000, 5000]

FAM = {
    "Meteora DLMM": "DLMM",
    "Pump Swap": "Pump",
    "Meteora DAMM V2": "DAMM",
    "Raydium Concentrated Liquidity": "CLMM",
    "Raydium CPMM": "CPMM",
    "Orca Whirlpools": "Orca",
    "Raydium Liquidity Pool V4": "RayV4",
    "Pancake Swap": "Pancake",
    "Manifest": "Manifest",
    "Meteora DAMM": "DAMM",
}

UNI = [
    ("A  DLMM+Pump", {"DLMM", "Pump"}),
    ("B  +DAMM v2", {"DLMM", "Pump", "DAMM"}),
    ("C  +Ray CLMM", {"DLMM", "Pump", "DAMM", "CLMM"}),
    ("D  +Ray CPMM", {"DLMM", "Pump", "DAMM", "CLMM", "CPMM"}),
    ("E  +Orca", {"DLMM", "Pump", "DAMM", "CLMM", "CPMM", "Orca"}),
]


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


def fams(dexes):
    return [FAM.get(d, d) for d in (dexes or [])]


def route_name(dexes):
    return " -> ".join(fams(dexes)) if dexes else "(none)"


def in_uni(dexes, allowed):
    fs = fams(dexes)
    return bool(fs) and all(f in allowed for f in fs)


def money(x):
    return f"${x:,.0f}"


def perh(x):
    return f"${x / HOURS:,.0f}/hr"


def load():
    meta = {}
    for line in PAIRS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        meta[p.get("mriya_sig")] = p
    rows = []
    for line in HITS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        h = json.loads(line)
        p = meta.get(h.get("mriya_sig")) or {}
        act = dt_us(h.get("mriya_rx0"), h.get("act_rx") if h.get("act_found") else None)
        first = dt_us(h.get("mriya_rx0"), h.get("trig_rx0") if h.get("trig_found") else None)
        rec = {
            "sig": h.get("mriya_sig"),
            "trig": h.get("trigger_sig") or p.get("trigger_sig"),
            "slot": h.get("slot") or p.get("slot"),
            "user": p.get("user"),
            "profit": float(p.get("profit") or 0),
            "dexes": tuple(p.get("dexes") or []),
            "route": route_name(p.get("dexes") or []),
            "hops": p.get("hops"),
            "dist": h.get("dist") if h.get("dist") is not None else p.get("dist"),
            "tick": p.get("tick") if p.get("tick") is not None else h.get("tick"),
            "leader": p.get("leader"),
            "provider": p.get("provider"),
            "headroom": act,
            "head_first": first,
            "located": bool(h.get("mriya_found") and h.get("trig_found") and h.get("act_found")),
            "searcher_found": bool(h.get("mriya_found")),
        }
        rows.append(rec)
    return rows, meta


def contest(rows, budget, pred=None):
    xs = [r for r in rows if r.get("located") and r.get("headroom") is not None and r["headroom"] >= budget]
    if pred:
        xs = [r for r in xs if pred(r)]
    return xs


def opp_groups(rows):
    g = defaultdict(list)
    for r in rows:
        if not r.get("trig") or r.get("slot") is None:
            continue
        g[(int(r["slot"]), r["trig"])].append(r)
    out = []
    for (slot, trig), xs in g.items():
        xs = sorted(xs, key=lambda r: (r["headroom"] is None, r["headroom"] if r["headroom"] is not None else 1e18))
        located = [r for r in xs if r.get("located") and r.get("headroom") is not None]
        if located:
            located = sorted(located, key=lambda r: r["headroom"])
            winner = located[0]
            second = located[1] if len(located) > 1 else None
            span = located[-1]["headroom"] - located[0]["headroom"]
        else:
            winner = xs[0]
            second = None
            span = None
        users = {r.get("user") for r in xs if r.get("user")}
        out.append(
            {
                "slot": slot,
                "trig": trig,
                "n": len(xs),
                "n_users": len(users),
                "users": users,
                "winner": winner,
                "second": second,
                "span": span,
                "first_profit": winner.get("profit") or 0,
                "total_profit": sum(r.get("profit") or 0 for r in xs),
                "headroom": winner.get("headroom") if winner.get("located") else None,
                "route": winner.get("route"),
                "mriya": MRIYA in users,
                "bq": BQ in users,
                "dtvm": DTVM in users,
                "rows": xs,
            }
        )
    return out


def main():
    if not HITS.exists() or not PAIRS.exists():
        print("missing hits/pairs", HITS.exists(), PAIRS.exists())
        sys.exit(1)
    rows, meta = load()
    located = [r for r in rows if r["located"]]
    total_arb = sum(float(p.get("profit") or 0) for p in meta.values())
    print(f"pairs {len(meta)} hits {len(rows)} located {len(located)}", flush=True)

    def sens(pred=None):
        return {b: sum(r["profit"] for r in contest(located, b, pred)) for b in BUDGETS}

    all_s = sens()
    r0 = lambda r: in_uni(r["dexes"], {"DLMM", "Pump"})
    exp = lambda r: in_uni(r["dexes"], {"DLMM", "Pump", "DAMM", "CLMM", "CPMM", "Orca"})
    r0_s = sens(r0)
    exp_s = sens(exp)

    # route family matrix
    by_route = defaultdict(list)
    for r in located:
        by_route[r["route"]].append(r)
    route_rows = []
    for name, xs in sorted(by_route.items(), key=lambda kv: -sum(r["profit"] for r in kv[1])):
        route_rows.append(
            {
                "route": name,
                "n": len(xs),
                "profit": sum(r["profit"] for r in xs),
                **{f"b{b}": sum(r["profit"] for r in xs if r["headroom"] >= b) for b in BUDGET_COLS},
            }
        )

    uni_tab = []
    for label, allowed in UNI:
        pred = lambda r, a=allowed: in_uni(r["dexes"], a)
        uni_tab.append(
            {
                "label": label,
                **{f"b{b}": sum(r["profit"] for r in contest(located, b, pred)) for b in BUDGET_COLS},
            }
        )

    # marginal ROI at 500us
    prev = 0.0
    roi = []
    for label, allowed in UNI:
        now = sum(r["profit"] for r in contest(located, 500, lambda r, a=allowed: in_uni(r["dexes"], a)))
        roi.append((label, now - prev, now))
        prev = now

    opps = opp_groups(located)
    # competition buckets
    buckets = [("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-10", 6, 10), ("10+", 11, 10**9)]
    comp_tab = []
    for lab, lo, hi in buckets:
        xs = [o for o in opps if lo <= o["n_users"] <= hi]
        profits = [o["first_profit"] for o in xs]
        comp_tab.append(
            {
                "lab": lab,
                "n": len(xs),
                "dol": sum(o["total_profit"] for o in xs),
                "med": pct(profits, 50),
                "p90": pct(profits, 90),
                "mx": max(profits) if profits else 0,
            }
        )

    # elite exclusion at 500us using winner headroom
    def elite_cut(pred):
        xs = [o for o in opps if o["headroom"] is not None and o["headroom"] >= 500 and pred(o)]
        return len(xs), sum(o["first_profit"] for o in xs), sum(o["total_profit"] for o in xs)

    elite_rows = [
        ("any", lambda o: True),
        ("no Mriya", lambda o: not o["mriya"]),
        ("no Mriya/4BQ", lambda o: not o["mriya"] and not o["bq"]),
        ("no Mriya/4BQ/Dtvmxr", lambda o: not o["mriya"] and not o["bq"] and not o["dtvm"]),
    ]

    fat_thr = [10, 25, 50, 100, 250, 500, 1000]
    fat = [r for r in located if r["profit"] >= 10]
    fat.sort(key=lambda r: -r["profit"])

    def jackpot(pmin, hmin, cmax):
        out = []
        for o in opps:
            if o["first_profit"] < pmin:
                continue
            if o["headroom"] is None or o["headroom"] < hmin:
                continue
            if o["n_users"] > cmax:
                continue
            out.append(o)
        out.sort(key=lambda o: -o["first_profit"])
        return out

    jp500 = jackpot(50, 500, 3)
    jp1ms = jackpot(50, 1000, 3)
    jp5ms = jackpot(50, 5000, 3)

    # score hunt
    scored = []
    for o in opps:
        if o["headroom"] is None or o["headroom"] <= 0 or o["n_users"] == 0:
            continue
        scored.append((o["first_profit"] * o["headroom"] / o["n_users"], o))
    scored.sort(reverse=True, key=lambda x: x[0])

    lines = []
    a = lines.append
    a("# SHRED_V1_MARKET")
    a("")
    a("3h18m premium shred window. Successful MEV.live arbs only.")
    a("Headroom = T(searcher first) - T(N actionable). No local budget subtracted.")
    a(f"Located both sides: {len(located)} / {len(meta)} pairs. Hours = {HOURS:.3f}.")
    a("Do not annualize. $/hr is this window only.")
    a("")
    a("## Headlines")
    a("")
    a("| | $ | $/hr |")
    a("|---|---:|---:|")
    a(f"| TOTAL SUCCESSFUL ARB | {money(total_arb)} | {perh(total_arb)} |")
    a(f"| SHRED-COMPETABLE (headroom ≥ 500 µs, all routes) | {money(all_s[500])} | {perh(all_s[500])} |")
    a(f"| CURRENT UNIVERSE (DLMM+Pump, ≥ 500 µs) | {money(r0_s[500])} | {perh(r0_s[500])} |")
    a(f"| EXPANDED (DLMM/Pump/DAMM/CLMM/CPMM/Orca, ≥ 500 µs) | {money(exp_s[500])} | {perh(exp_s[500])} |")
    a("")
    a("## Sensitivity — captured competitor $ with enough headroom")
    a("")
    hdr = "| budget | all routes | route0 DLMM+Pump | expanded |"
    a(hdr)
    a("|---:|---:|---:|---:|")
    for b in BUDGETS:
        lab = f"{b} µs" if b < 1000 else f" {b/1000:.0f} ms" if b % 1000 == 0 else f" {b/1000:.1f} ms"
        if b >= 1000:
            lab = f"{b/1000:g} ms"
        else:
            lab = f"{b} µs"
        a(f"| {lab} | {money(all_s[b])} | {money(r0_s[b])} | {money(exp_s[b])} |")
    a("")
    a("## Sensitivity × universe")
    a("")
    a("| universe | 50µs | 100µs | 250µs | 500µs | 1ms | 5ms |")
    a("|---|---:|---:|---:|---:|---:|---:|")
    a(
        f"| all routes | {money(all_s[50])} | {money(all_s[100])} | {money(all_s[250])} | {money(all_s[500])} | {money(all_s[1000])} | {money(all_s[5000])} |"
    )
    a(
        f"| route0 | {money(r0_s[50])} | {money(r0_s[100])} | {money(r0_s[250])} | {money(r0_s[500])} | {money(r0_s[1000])} | {money(r0_s[5000])} |"
    )
    a(
        f"| expanded | {money(exp_s[50])} | {money(exp_s[100])} | {money(exp_s[250])} | {money(exp_s[500])} | {money(exp_s[1000])} | {money(exp_s[5000])} |"
    )
    a("")
    a("## Dollars by route family")
    a("")
    a("| route | n | all $ | 100µs | 250µs | 500µs | 1ms | 5ms |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in route_rows[:25]:
        a(
            f"| {row['route']} | {row['n']} | {money(row['profit'])} | "
            f"{money(row['b100'])} | {money(row['b250'])} | {money(row['b500'])} | "
            f"{money(row['b1000'])} | {money(row['b5000'])} |"
        )
    a("")
    a("## Protocol addition ROI (marginal capturable $ at ≥ 500 µs)")
    a("")
    a("| add | extra $ | extra $/hr | cumulative |")
    a("|---|---:|---:|---:|")
    for label, extra, cum in roi:
        a(f"| {label} | {money(extra)} | {perh(extra)} | {money(cum)} |")
    a("")
    a("## Competition")
    a("")
    a("| competitors | opportunities | $ extracted | median first $ | p90 | max |")
    a("|---|---:|---:|---:|---:|---:|")
    for c in comp_tab:
        med = f"{c['med']:.2f}" if c["med"] is not None else "—"
        p90 = f"{c['p90']:.2f}" if c["p90"] is not None else "—"
        a(f"| {c['lab']} | {c['n']} | {money(c['dol'])} | {med} | {p90} | {c['mx']:.1f} |")
    a("")
    a("## Elite absent (winner headroom ≥ 500 µs)")
    a("")
    a("| exclusion | opps | winner $ | all extracted $ |")
    a("|---|---:|---:|---:|")
    for lab, pred in elite_rows:
        n, w, t = elite_cut(pred)
        a(f"| {lab} | {n} | {money(w)} | {money(t)} |")
    a("")
    a("## Jackpot  profit≥$50 ∧ competitors≤3")
    a("")
    for title, xs in (("≥ 500 µs", jp500), ("≥ 1 ms", jp1ms), ("≥ 5 ms", jp5ms)):
        a(f"### {title}  n={len(xs)}  winner $={sum(o['first_profit'] for o in xs):.0f}")
        a("")
        a("| profit | headroom | n | route | winner | Mriya | 4BQ | tick | leader |")
        a("|---:|---:|---:|---|---|---|---|---:|---|")
        for o in xs[:40]:
            w = o["winner"]
            a(
                f"| {o['first_profit']:.1f} | {o['headroom']/1000:.2f} ms | {o['n_users']} | "
                f"{o['route']} | {SHORT.get(w.get('user'), (w.get('user') or '?')[:8])} | "
                f"{'Y' if o['mriya'] else ''} | {'Y' if o['bq'] else ''} | "
                f"{w.get('tick') if w.get('tick') is not None else ''} | {w.get('leader') or ''} |"
            )
        a("")
    a("## Fat tail (winner ≥ $10, located)")
    a("")
    a("| ≥$ | n | $ | ≥500µs n | ≥500µs $ |")
    a("|---:|---:|---:|---:|---:|")
    for thr in fat_thr:
        xs = [r for r in located if r["profit"] >= thr]
        ys = [r for r in xs if r["headroom"] >= 500]
        a(f"| {thr} | {len(xs)} | {money(sum(r['profit'] for r in xs))} | {len(ys)} | {money(sum(r['profit'] for r in ys))} |")
    a("")
    a("## Top scored  profit × headroom / competitors")
    a("")
    a("| score | profit | headroom | n | route | winner | elite |")
    a("|---:|---:|---:|---:|---|---|---|")
    for sc, o in scored[:30]:
        w = o["winner"]
        elite = ",".join(x for x, f in (("Mriya", o["mriya"]), ("4BQ", o["bq"]), ("Dtvm", o["dtvm"])) if f) or ""
        a(
            f"| {sc:,.0f} | {o['first_profit']:.1f} | {o['headroom']/1000:.2f} ms | {o['n_users']} | "
            f"{o['route']} | {SHORT.get(w.get('user'), (w.get('user') or '?')[:8])} | {elite} |"
        )
    a("")
    a("Uncaptured residual alpha (N with no successful searcher) is not in this census.")
    text = "\n".join(lines) + "\n"
    MD.write_text(text, encoding="utf-8")
    print(text[:2500])
    print("wrote", MD)

    summary = {
        "hours": HOURS,
        "total_arb": total_arb,
        "located": len(located),
        "pairs": len(meta),
        "all": all_s,
        "route0": r0_s,
        "expanded": exp_s,
        "routes": route_rows[:25],
        "roi": [{"label": l, "extra": e, "cum": c} for l, e, c in roi],
        "comp": comp_tab,
        "jackpot_500": len(jp500),
        "jackpot_500_usd": sum(o["first_profit"] for o in jp500),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
