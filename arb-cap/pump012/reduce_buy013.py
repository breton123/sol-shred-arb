#!/usr/bin/env python3
"""PUMP-BUY-013 reducer. Frozen soak only. Does not deploy.

The 1003 are buy_exact_quote_in rows where virtual recovers base vault
but quote-vault delta still misses. Hunt one fee/config formula.
Zero regression on the 2537 both-vault virtual hits (almost all sells).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from pump_apply import apply_swap, invert_virtual
from replay import replay_one, _dir_amt


def ceil_div(n: int, d: int) -> int:
    return n // d + (1 if n % d else 0)


def fee(n: int, bps: int) -> int:
    return ceil_div(n * bps, 10000) if bps else 0


def floor_fee(n: int, bps: int) -> int:
    return n * bps // 10000 if bps else 0


def pred_buy_quote(sb: dict, ain: int) -> tuple[int, dict]:
    """Current kernel: vault += ain - proto - creator (LP stays)."""
    lp_b = int(sb.get("lp_fee_bps") or 0)
    pr_b = int(sb.get("protocol_fee_bps") or 0)
    cr_b = int(sb.get("creator_fee_bps") or 0)
    total = lp_b + pr_b + cr_b
    eff = ain * 10000 // (10000 + total) if total < 10000 else 0
    lp, pr, cr = fee(eff, lp_b), fee(eff, pr_b), fee(eff, cr_b)
    pred = ain - pr - cr
    return pred, {
        "lp": lp, "proto": pr, "creator": cr, "effective": eff,
        "lp_bps": lp_b, "proto_bps": pr_b, "creator_bps": cr_b,
    }


def load_pools(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    rows = raw if isinstance(raw, list) else (raw.get("pools") or raw.get("by_idx") or [])
    if isinstance(raw, dict) and not rows:
        for k, v in raw.items():
            if isinstance(v, dict) and ("pubkey" in v or "quote" in v or "my" in v):
                try:
                    out[int(k)] = v
                except ValueError:
                    pass
        return out
    for p in rows:
        if not isinstance(p, dict):
            continue
        idx = p.get("idx")
        if idx is None:
            continue
        out[int(idx)] = p
    return out


def quote_mint(pools: dict, idx, bundle: dict) -> str:
    p = pools.get(int(idx)) if idx is not None else None
    if isinstance(p, dict):
        for k in ("quote", "my", "mint_y", "quote_mint"):
            v = p.get(k)
            if isinstance(v, str) and v:
                return v
    return "?"


def collect(misdir: Path, pools: dict) -> tuple[list, list]:
    buys, cleans = [], []
    for p in misdir.glob("*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if b.get("kind") != "pump":
            continue
        tag = replay_one(b)
        if tag == "explained_virtual":
            cleans.append(b)
        elif tag == "explained_virtual_fee_residual":
            buys.append(b)
    return buys, cleans


def analyze_buy(b: dict, pools: dict) -> dict | None:
    sb, pu = b.get("s_before") or {}, b.get("published_s") or {}
    d, ain = _dir_amt(b)
    if d != 0 or ain is None:
        return None
    pred, fees = pred_buy_quote(sb, ain)
    pub_dq = int(pu["reserve_quote"]) - int(sb["reserve_quote"])
    res = pred - pub_dq
    idx = b.get("idx")
    bps = round(res * 10000 / ain) if ain else None
    hits = {
        "res==lp": res == fees["lp"],
        "res==proto": res == fees["proto"],
        "res==creator": res == fees["creator"],
        "res==lp+proto+creator": res == fees["lp"] + fees["proto"] + fees["creator"],
        "res==ain-pub": res == ain - pub_dq,
        "pub==ain": pub_dq == ain,
        "pub==eff": pub_dq == fees["effective"],
        "pub==ain-allfees": pub_dq == ain - fees["lp"] - fees["proto"] - fees["creator"],
        "pub==ain-pr-cr": pub_dq == pred,
        "pub==eff-pr-cr": pub_dq == fees["effective"] - fees["proto"] - fees["creator"],
    }
    # invert extra bps on ain / effective (ceil and floor)
    extra = {}
    for name, n, fn in (
        ("ceil_ain", ain, fee),
        ("floor_ain", ain, floor_fee),
        ("ceil_eff", fees["effective"], fee),
        ("floor_eff", fees["effective"], floor_fee),
    ):
        found = None
        for bps_i in range(0, 2001):
            if fn(n, bps_i) == res:
                found = bps_i
                break
        extra[name] = found
    # invert creator_bps in kernel identity: pub = ain - fee(eff', proto) - fee(eff', cr)
    # eff' depends on total bps. Search creator_bps.
    cr_hit = None
    for cr in range(0, 501):
        tot = fees["lp_bps"] + fees["proto_bps"] + cr
        if tot >= 10000:
            break
        eff = ain * 10000 // (10000 + tot)
        pr = fee(eff, fees["proto_bps"])
        c = fee(eff, cr)
        if ain - pr - c == pub_dq:
            cr_hit = cr
            break
    return {
        "idx": idx,
        "pool": b.get("pool"),
        "ain": ain,
        "pred_dq": pred,
        "pub_dq": pub_dq,
        "residual": res,
        "residual_bps": bps,
        "fees": fees,
        "hits": hits,
        "extra_bps": extra,
        "creator_bps_hit": cr_hit,
        "quote_mint": quote_mint(pools, idx, b),
        "disabled": sb.get("disabled"),
        "status": sb.get("status"),
    }


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/data/bsc/captures/soak_fastsoak_20260925/state008")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent
    pools = load_pools(root / "POOLS.json")
    if not pools:
        pools = load_pools(Path("/home/louis/captures/paper_orbit/liveuniv.json"))
    buys, cleans = collect(root / "mismatch", pools)
    rows = [analyze_buy(b, pools) for b in buys]
    rows = [r for r in rows if r]

    hit_n = Counter()
    extra_n = Counter()
    cr_n = Counter()
    mint_n = Counter()
    bps_n = Counter()
    idx_n = Counter()
    sign_n = Counter()
    for r in rows:
        for k, v in r["hits"].items():
            if v:
                hit_n[k] += 1
        for k, v in r["extra_bps"].items():
            extra_n[f"{k}={v}"] += 1
        cr_n[r["creator_bps_hit"]] += 1
        mint_n[r["quote_mint"][:12]] += 1
        bps_n[r["residual_bps"]] += 1
        idx_n[r["idx"]] += 1
        sign_n["pos" if r["residual"] > 0 else "neg" if r["residual"] < 0 else "zero"] += 1

    # sell regression: V invert still both-vault exact
    sell_ok = 0
    sell_fail = 0
    for b in cleans:
        d, ain = _dir_amt(b)
        if d != 1:
            continue
        v = invert_virtual(b["s_before"], ain, 1, b.get("published_s") or {})
        if v is None:
            sell_fail += 1
            continue
        g = apply_swap({**b["s_before"], "virtual_quote": v}, ain, 1)
        pu = b.get("published_s") or {}
        if g and g["reserve_base"] == int(pu["reserve_base"]) and g["reserve_quote"] == int(pu["reserve_quote"]):
            sell_ok += 1
        else:
            sell_fail += 1

    doc = {
        "n_buy_residual": len(rows),
        "n_clean_virtual": len(cleans),
        "sell_regression": {"ok": sell_ok, "fail": sell_fail},
        "residual_sign": dict(sign_n),
        "formula_hits": dict(hit_n.most_common()),
        "extra_bps": dict(extra_n.most_common(20)),
        "creator_bps_hit": {str(k): v for k, v in cr_n.most_common(15)},
        "residual_bps_hist": {str(k): v for k, v in bps_n.most_common(20)},
        "quote_mint": dict(mint_n.most_common(12)),
        "top_pools": dict(idx_n.most_common(12)),
        "examples": rows[:8],
    }
    # Best single extra_bps key
    best_extra = extra_n.most_common(1)
    doc["dominant_extra"] = best_extra[0] if best_extra else None
    out.mkdir(parents=True, exist_ok=True)
    (out / "PUMP013_REDUCE.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# PUMP-BUY-013 reducer",
        "",
        f"buy fee residuals: {len(rows)}",
        f"clean virtual (2537 class): {len(cleans)}  sell replay ok={sell_ok} fail={sell_fail}",
        f"residual sign: {dict(sign_n)}",
        "",
        "## formula hits (count of rows explained)",
    ]
    for k, v in hit_n.most_common():
        lines.append(f"- {k}: {v} ({100*v/len(rows):.1f}%)" if rows else f"- {k}: {v}")
    lines += ["", "## extra bps invert (top)", ""]
    for k, v in extra_n.most_common(12):
        lines.append(f"- {k}: {v}")
    lines += ["", "## creator_bps that reproduces pub quote", ""]
    for k, v in cr_n.most_common(10):
        lines.append(f"- {k}: {v}")
    lines += ["", "## residual as bps of amount_in (top)", ""]
    for k, v in bps_n.most_common(10):
        lines.append(f"- {k} bps: {v}")
    lines += ["", "## quote mint", ""]
    for k, v in mint_n.most_common(8):
        lines.append(f"- {k}: {v}")
    md = "\n".join(lines) + "\n"
    (out / "PUMP013_REDUCE.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
