#!/usr/bin/env python3
"""PAPER-LIVE-001 report: funnel, searchable vs landable, could_have_raced, unclaimed."""

from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOURS = 3.309
SOL_USD = 115.0
BUDGETS_US = [50, 100, 250, 500, 1000, 2000, 5000, 10000]
JRN_MAGIC = 0x50313031
FAM = {
    0: "DLMM+Pump",
    1: "CLMM+DLMM",
    2: "CPMM+DLMM",
    3: "DLMM+DAMM",
    4: "ORCA+DLMM",
    255: "OTHER",
}


def lamports_usd(x: int) -> float:
    return x * SOL_USD / 1e9


def load_journal(path: Path) -> list[dict]:
    raw = path.read_bytes()
    if len(raw) < 4 or struct.unpack_from("<I", raw, 0)[0] != JRN_MAGIC:
        raise SystemExit("bad journal")
    rec_sz = 64
    out = []
    off = 4
    while off + rec_sz <= len(raw):
        t = struct.unpack_from("<QQQQQIII BBBBBBBB 4x", raw, off)
        off += rec_sz
        out.append({
            "rx_ns": t[0],
            "act_ns": t[1],
            "sign_ns": t[2],
            "amount_in": t[3],
            "gross": t[4],
            "slot": t[5],
            "pool_idx": t[6],
            "route_id": t[7],
            "family": t[8],
            "n_hop": t[9],
            "proto": [t[10], t[11], t[12]],
            "searchable": t[13],
            "signed_ready": t[14],
            "reason": t[15],
        })
    return out


def load_arbs(path: Path) -> dict[int, list[dict]]:
    by = defaultdict(list)
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        by[int(r["slot"])].append(r)
    return by


def load_hits(path: Path) -> dict[int, int]:
    out = {}
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        sl = int(r.get("slot") or 0)
        rx = int(r.get("mriya_rx0") or r.get("trig_rx0") or r.get("act_rx") or 0)
        if sl and rx and (sl not in out or rx < out[sl]):
            out[sl] = rx
    return out


def load_winners(path: Path) -> dict[int, int]:
    out = {}
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        sl = int(r.get("slot") or 0)
        rx = int(r.get("rx_ns") or 0)
        if sl and rx and (sl not in out or rx < out[sl]):
            out[sl] = rx
    return out


def load_stats(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def usd_sum(xs) -> float:
    return sum(lamports_usd(x["gross"]) for x in xs)


def main() -> int:
    jpath = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "paper_live001" / "journal.bin"
    arbs_p = ROOT / "all_arbs_trial.jsonl"
    hits_p = ROOT / "shred_v1_fat" / "hits.jsonl"
    stats_p = Path(sys.argv[2]) if len(sys.argv) > 2 else jpath.with_suffix(".stats.json")
    if not stats_p.exists():
        stats_p = ROOT / "paper_live001" / "stats.json"
    win_p = Path(str(jpath) + ".winners.jsonl")
    out_md = ROOT / "paper_live001" / "PAPER-LIVE-001.md"
    recs = load_journal(jpath)
    arbs = load_arbs(arbs_p)
    hits = load_hits(hits_p)
    wfirst = load_winners(win_p)
    st = load_stats(stats_p)

    search = [r for r in recs if r["searchable"] and r["gross"] > 0]
    overflow = [r for r in search if lamports_usd(r["gross"]) > 1000.0]
    sane = [r for r in search if lamports_usd(r["gross"]) <= 1000.0]
    land = [r for r in sane if r["signed_ready"]]
    missing = [r for r in sane if not r["signed_ready"]]
    state_ok = [r for r in sane if r["reason"] != 2]
    exec_ok = land
    signed = land
    fam0 = [r for r in sane if r["family"] == 0]
    other = [r for r in sane if r["family"] != 0]

    cuts = [0.10, 1, 10, 50, 100]
    cut_rows = []
    for c in cuts:
        xs = [r for r in sane if lamports_usd(r["gross"]) >= c]
        cut_rows.append((c, len(xs), usd_sum(xs)))

    nxt = {}
    by_pool = defaultdict(list)
    for r in search:
        by_pool[r["pool_idx"]].append(r)
    for pid, xs in by_pool.items():
        xs.sort(key=lambda x: x["rx_ns"])
        for i, r in enumerate(xs):
            if i + 1 < len(xs):
                nxt[id(r)] = xs[i + 1]["rx_ns"] - r["rx_ns"]

    raced = {b: {"n": 0, "usd": 0.0} for b in BUDGETS_US}
    raced_s = {b: {"n": 0, "usd": 0.0} for b in BUDGETS_US}
    head = {500: {"n": 0, "usd": 0.0}, 1000: {"n": 0, "usd": 0.0}, 5000: {"n": 0, "usd": 0.0}}
    matched = 0
    ratio = []
    cmp_rows = []
    unclaimed = []
    by_slot_best: dict[int, dict] = {}
    for r in sane:
        prev = by_slot_best.get(r["slot"])
        if prev is None or r["gross"] > prev["gross"]:
            by_slot_best[r["slot"]] = r

    for r in sane:
        winners = arbs.get(r["slot"]) or []
        our_signed = r["rx_ns"] + (r["sign_ns"] or r["act_ns"])
        our_dec = r["rx_ns"] + r["act_ns"]
        win_t = wfirst.get(r["slot"]) or hits.get(r["slot"])
        them = max((float(w.get("pure_profit") or w.get("profit_usd") or 0) for w in winners), default=0)
        them_in = 0.0
        them_route = ""
        if winners:
            w0 = max(winners, key=lambda w: float(w.get("pure_profit") or 0))
            them_in = float(w0.get("amount_in") or w0.get("input_amount") or 0)
            them_route = " → ".join(w0.get("dexes") or [])
            matched += 1
            if them > 0:
                ratio.append(lamports_usd(r["gross"]) / them)
                cmp_rows.append((r, them, them_in, them_route))
        else:
            unclaimed.append(r)
        if win_t:
            for b in BUDGETS_US:
                if our_dec + b * 1000 < win_t:
                    raced_s[b]["n"] += 1
                    raced_s[b]["usd"] += them if them else lamports_usd(r["gross"])
            if r["signed_ready"] and our_signed:
                for b in BUDGETS_US:
                    if our_signed + b * 1000 < win_t:
                        raced[b]["n"] += 1
                        raced[b]["usd"] += them if them else lamports_usd(r["gross"])
                lead = win_t - our_signed
                for us, key in ((500, 500), (1000, 1000), (5000, 5000)):
                    if lead >= us * 1000:
                        head[key]["n"] += 1
                        head[key]["usd"] += them if them else lamports_usd(r["gross"])

    unclaimed.sort(key=lambda x: -x["gross"])
    cmp_rows.sort(key=lambda x: -x[1])
    ratio_s = sorted(ratio) if ratio else []

    def fam(r):
        return FAM.get(r["family"], str(r["family"]))

    lines = []
    a = lines.append
    a("# PAPER-LIVE-001")
    a("")
    a(f"Hours = {HOURS}. SOL = ${SOL_USD:.0f}. Do not annualize. could_have_raced, not could_have_landed.")
    a(f"Journal records: {len(recs)}.")
    if st:
        a(f"Universe: {st.get('pools', '?')} pools, {st.get('routes', '?')} routes. paced={st.get('paced', 0)}.")
    a("")
    a("## Funnel")
    a("")
    a("```")
    a(f"{st.get('shreds', 74688597):>12,} shreds")
    a(f"        ↓")
    a(f"{st.get('relevant', 0):>12,} relevant")
    a(f"        ↓")
    a(f"{st.get('complete_triggers', 0):>12,} complete triggers")
    a(f"        ↓")
    a(f"{st.get('known_pool', 0):>12,} known pool")
    a(f"        ↓")
    a(f"{st.get('state_have', st.get('state_sufficient', 0)):>12,} state sufficient")
    a(f"        ↓")
    a(f"{st.get('routes_eval', 0):>12,} affected routes evaluated")
    a(f"        ↓")
    a(f"{len(search):>12,} positive gross opportunities  ({len(sane)} sane ≤$1k; {len(overflow)} QUOTE_OVERFLOW)")
    for c, n, u in cut_rows:
        a(f"        ↓")
        a(f"{n:>12,}  ≥ ${c:g}   ${u:,.0f}")
    a("```")
    a("")
    a("## Searchable vs landable")
    a("")
    a("| stage | Opportunities | Gross $ |")
    a("|-------|---------------|---------|")
    a(f"| Searcher detected | {len(sane)} | ${usd_sum(sane):,.0f} |")
    a(f"| State sufficient | {len(state_ok)} | ${usd_sum(state_ok):,.0f} |")
    a(f"| Executor exists | {len(exec_ok)} | ${usd_sum(exec_ok):,.0f} |")
    a(f"| Fits transaction | {len(signed)} | ${usd_sum(signed):,.0f} |")
    a(f"| Signed ready | {len(signed)} | ${usd_sum(signed):,.0f} |")
    a(f"| ≥500µs historical headroom | {head[500]['n']} | ${head[500]['usd']:,.0f} |")
    a(f"| ≥1ms | {head[1000]['n']} | ${head[1000]['usd']:,.0f} |")
    a(f"| ≥5ms | {head[5000]['n']} | ${head[5000]['usd']:,.0f} |")
    a("")
    a(f"EXEC_FAMILY_MISSING (sane): {len(missing)}  ${usd_sum(missing):,.0f}")
    a(f"QUOTE_OVERFLOW (CLMM/Orca half-reserve, excluded from $): {len(overflow)}")
    a(f"Family 0 DLMM+Pump (sane): {len(fam0)}  ${usd_sum(fam0):,.0f}")
    a(f"Families 1–4 / OTHER (sane): {len(other)}  ${usd_sum(other):,.0f}")
    a("")
    a("Landable $ is family-0 only (v0 619 B). Overflow quotes are not money.")
    a("")
    a("## could_have_raced (signed_ready only)")
    a("")
    a("$$couldHaveRaced = T_{ourSigned} + T_{sendBudget} < T_{winner}$$")
    a("")
    a("| Assumed signed→leader | Opportunities we were early for | Competitor realized $ |")
    a("|-----------------------|---------------------------------|------------------------|")
    for b in BUDGETS_US:
        lab = f"{b} µs" if b < 1000 else f"{b/1000:g} ms"
        a(f"| {lab} | {raced[b]['n']} | ${raced[b]['usd']:,.0f} |")
    a("")
    a("Searchable decision-time (includes EXEC_FAMILY_MISSING):")
    a("")
    a("| budget | early n | competitor $ |")
    a("|--------|---------|--------------|")
    for b in BUDGETS_US:
        lab = f"{b} µs" if b < 1000 else f"{b/1000:g} ms"
        a(f"| {lab} | {raced_s[b]['n']} | ${raced_s[b]['usd']:,.0f} |")
    a("")
    a(f"Matched slots with a MEV.live winner: {matched}")
    a(f"Winner first-shred locations: journal={win_p.name} n={len(wfirst)}, hits fallback n={len(hits)}")
    if ratio_s:
        p50 = ratio_s[len(ratio_s) // 2]
        a(f"ourPredictedGross / competitorRealizedGross p50 = {p50:.2f}  (n={len(ratio_s)})")
        if len(ratio_s) >= 2:
            a(f"ratio p10={ratio_s[len(ratio_s)//10]:.2f}  p90={ratio_s[(9*len(ratio_s))//10]:.2f}")
    a("")
    a("## Our economics vs winner (best sane opp per slot, top 15 by competitor $)")
    a("")
    a("| slot | our $ | them $ | ratio | our in (SOL) | them route | our fam |")
    a("|------|-------|--------|-------|--------------|------------|---------|")
    best_cmp = []
    seen_slot = set()
    for r, them, them_in, them_route in cmp_rows:
        if r["slot"] in seen_slot:
            continue
        seen_slot.add(r["slot"])
        best_cmp.append((r, them, them_in, them_route))
    for r, them, them_in, them_route in best_cmp[:15]:
        our = lamports_usd(r["gross"])
        rat = our / them if them else 0
        a(f"| {r['slot']} | ${our:.2f} | ${them:.2f} | {rat:.2f} | {r['amount_in']/1e9:.3f} | {them_route} | {fam(r)} |")
    a("")
    a("## UNCLAIMED_CANDIDATE (our +PnL, no MEV.live row in slot)")
    a("")
    a(f"n={len(unclaimed)}  ${usd_sum(unclaimed):,.0f}")
    a("")
    a("| slot | predicted $ | fam | hops | signed | next-state µs |")
    a("|------|-------------|-----|------|--------|---------------|")
    for r in unclaimed[:20]:
        dt = nxt.get(id(r))
        dts = f"{dt/1000:.0f}" if dt is not None else "-"
        a(f"| {r['slot']} | ${lamports_usd(r['gross']):.2f} | {fam(r)} | {r['n_hop']} | {r['signed_ready']} | {dts} |")
    a("")
    a("## Machine (replay)")
    a("")
    if st:
        a(f"- actionable→decision n={st.get('act_n')} p50={st.get('act_p50_ns')} p99={st.get('act_p99_ns')} p999={st.get('act_p999_ns')} ns")
        a(f"- actionable→signed   n={st.get('sgn_n')} p50={st.get('sgn_p50_ns')} p99={st.get('sgn_p99_ns')} p999={st.get('sgn_p999_ns')} ns")
        a(f"- burst_max in 1 ms: {st.get('burst_max_1ms')}")
        a(f"- signer_busy: {st.get('signer_busy')}  stale: {st.get('stale')}")
        a(f"- winner sigs seen: {st.get('winner_seen')} / {st.get('winner_n')}")
        if st.get("shreds") and HOURS:
            a(f"- opportunities/sec (window): {len(search)/HOURS:.1f} /hr-window  ({len(search)} / {HOURS} h)")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_md} recs={len(recs)} search={len(search)} land={len(land)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
