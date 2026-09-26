#!/usr/bin/env python3
"""Reclassify the already-fetched sample. No RPC."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\alpha_census")
QUOTE = {
    "So11111111111111111111111111111111111111112",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}
SEARCHERS = {
    "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X": "Mriya",
    "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK": "4BQ",
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "Dtvmxr",
    "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu": "7dGrdJ",
    "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd": "gtagyE",
    "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4": "9EwQoN",
}


def snake(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def family(ix: str) -> str:
    n = snake(ix)
    if n in (
        "swap", "swap2", "swap_exact_out", "swap_exact_out2",
        "swap_with_price_impact", "swap_with_price_impact2",
        "buy", "buy_exact_quote_in", "sell",
    ):
        return "swap"
    if n.startswith("add_liquidity") or n.startswith("remove_liquidity") or n in (
        "rebalance_liquidity", "deposit", "withdraw",
    ):
        return "liquidity"
    if n in ("close_position", "close_position2"):
        return "liquidity"
    if n.startswith("initialize_lb_pair") or n.startswith("initialize_customizable") or n.startswith("initialize_permission") or n in (
        "create_pool", "set_activation_point", "set_pair_status", "set_pair_status_permissionless", "disable",
    ):
        return "lifecycle"
    if n in ("go_to_a_bin",) or n.startswith("initialize_bin_array") or n == "increase_oracle_length":
        return "admin_state"
    if "limit_order" in n:
        return "limit_order"
    if "fee" in n or n.startswith("claim_") or n.startswith("collect_"):
        return "fee_config"
    return "other"


def bucket(ixs: list[str]) -> str:
    if not ixs:
        return "no_invoke"
    fams = [family(x) for x in ixs]
    if "swap" in fams and "liquidity" in fams:
        return "swap+liquidity"
    for name in ("swap", "liquidity", "lifecycle", "fee_config", "admin_state", "limit_order"):
        if name in fams:
            return name
    return "other"


def main() -> None:
    sample = [json.loads(l) for l in (OUT / "sample.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    arbs = [json.loads(l) for l in (OUT / "mev_window.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_mint = defaultdict(list)
    for a in arbs:
        if a.get("mint") and a.get("slot") is not None:
            by_mint[a["mint"]].append(a)
    rows = []
    for rec in sample:
        if not rec.get("ok"):
            continue
        ixs = rec.get("ixs") or []
        b = bucket(ixs)
        mints = [m for m in (rec.get("mints") or []) if m not in QUOTE]
        slot = int(rec.get("sig_slot") or 0)
        hits = []
        for m in mints:
            for a in by_mint.get(m, []):
                ds = int(a["slot"]) - slot
                if 0 <= ds <= 5:
                    hits.append(a)
        hits.sort(key=lambda a: (int(a["slot"]), -float(a.get("usd") or 0)))
        elite = sorted({SEARCHERS[h["user"]] for h in hits if h.get("user") in SEARCHERS})
        taker = "NO_MINT_MATCH" if not hits else ("ELITE" if elite else "OTHER_TAKER")
        rows.append({
            "signature": rec.get("sig"),
            "slot": slot,
            "program": rec.get("program"),
            "trigger_class": b,
            "instructions": ixs,
            "effects": sorted({census_effect(snake(i)) for i in ixs}) if ixs else [],
            "mints": mints[:4],
            "taker": taker,
            "elite": elite,
            "slots_to_taker": (int(hits[0]["slot"]) - slot) if hits else None,
            "state_confidence": "STATE_UNAVAILABLE",
            "edge_before": None,
            "edge_after": None,
            "optimal_gross": None,
            "preexec": preexec(b),
        })
    (OUT / "UNCAPTURED.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows if r["trigger_class"] not in ("swap", "no_invoke") and r["taker"] == "NO_MINT_MATCH"),
        encoding="utf-8",
    )
    (OUT / "joined2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    acc = {}
    for r in rows:
        k = (r["program"], r["trigger_class"])
        a = acc.setdefault(k, {"n": 0, "taker": 0, "elite": 0, "ix": Counter(), "dt": []})
        a["n"] += 1
        if r["taker"] != "NO_MINT_MATCH":
            a["taker"] += 1
        if r["elite"]:
            a["elite"] += 1
        if r["slots_to_taker"] is not None:
            a["dt"].append(r["slots_to_taker"])
        for ix in r["instructions"]:
            a["ix"][ix] += 1
    print(f"{'prog':<6} {'class':<16} {'n':>5} {'taker%':>7} {'elite%':>7} {'med_slots':>9}")
    for (prog, cls), a in sorted(acc.items(), key=lambda kv: (kv[0][0], -kv[1]["n"])):
        dt = sorted(a["dt"])
        med = dt[len(dt) // 2] if dt else None
        print(f"{prog:<6} {cls:<16} {a['n']:5} {100*a['taker']/a['n']:7.1f} {100*a['elite']/a['n']:7.1f} {str(med):>9}  {a['ix'].most_common(4)}")
    print("uncaptured_non_swap", sum(1 for r in rows if r["trigger_class"] not in ("swap", "no_invoke") and r["taker"] == "NO_MINT_MATCH"))
    print("invoked", sum(1 for r in rows if r["trigger_class"] != "no_invoke"), "of", len(rows))
    print("mev", len(arbs), "usd", round(sum(float(a.get("usd") or 0) for a in arbs), 1))


def census_effect(n: str) -> str:
    return census.EFFECT.get(n, "UNKNOWN") if False else {
        # local, snake names
    }.get(n, "SEE")


def preexec(b: str) -> str:
    if b == "swap":
        return "PREEXEC_EXACT"
    if b == "liquidity":
        return "PREEXEC_DETERMINISTIC_WITH_STATE"
    if b in ("fee_config", "admin_state", "lifecycle"):
        return "PREEXEC_PARTIAL"
    if b == "no_invoke":
        return "POSTEXEC_ONLY"
    return "UNKNOWN"


# fix effects properly
import census as census_mod

def census_effect(n: str) -> str:
    return census_mod.EFFECT.get(n, "UNKNOWN")


if __name__ == "__main__":
    main()
