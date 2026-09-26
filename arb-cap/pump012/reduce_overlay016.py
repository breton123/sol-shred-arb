#!/usr/bin/env python3
"""PUMP-TX-016 overlay replay of the frozen Pump soak. No deploy.

Combines virtual (from S_before only), FEE-015 schedule, every Pump CPI
in execution order, buy_exact_out, per-CPI identity, terminal overlay.

Residuals are only:
  bit_exact | unsupported_cpi | missing_state | association_ambiguity | publication_order
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

from pump_apply import apply_swap
from pump_fee import parse_fee_config, parse_global_config, parse_pool_meta
from pump_overlay import (
    MODEL,
    apply_sequence,
    classify_overlay,
    cpis_for_pool,
    fee_overlay_state,
    vaults,
)
from replay import _dir_amt, replay_one

BUCKETS = (
    "bit_exact",
    "unsupported_cpi",
    "missing_state",
    "association_ambiguity",
    "publication_order",
)


def load_cfg(path: Path) -> tuple[dict | None, dict | None]:
    fp = path / "PUMP015_FEE.json"
    if not fp.exists():
        return None, None
    raw = json.loads(fp.read_text())
    cfg = raw.get("config") or {}
    # reconstruct minimal fee_cfg / gcfg for resolve_fee_state
    fee_cfg = {
        "flat_fees": cfg.get("flat_fees") or {"lp_fee_bps": 25, "protocol_fee_bps": 5, "creator_fee_bps": 0},
        "fee_tiers": [
            {"market_cap_lamports_threshold": t, "fees": f}
            for t, f in zip(cfg.get("tier_thresholds") or [], cfg.get("tier_fees") or [])
        ],
        "stable_fee_tiers": [],
        "exotic_flat_fees": cfg.get("exotic_flat_fees") or {},
    }
    g = cfg.get("global") or {}
    return fee_cfg, g


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/data/bsc/captures/soak_fastsoak_20260925/state008")
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    meta = {int(p["idx"]): p for p in u.get("pools") or []}
    fee_cfg, gcfg = load_cfg(outdir)

    txdir = outdir / "n015_tx"
    fee_tx = outdir / "fee014_tx"
    cache = {}
    for d in (txdir, fee_tx):
        if not d.is_dir():
            continue
        for fp in d.glob("*.json"):
            cache[fp.stem] = json.loads(fp.read_text())

    n = Counter()
    old = Counter()
    overlay_n = 0
    examples = {k: [] for k in BUCKETS}
    sells_two_leg = 0

    for p in (root / "mismatch").glob("*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if b.get("kind") != "pump":
            continue
        tag = replay_one(b)
        old[tag] += 1
        sb, pu = b.get("s_before") or {}, b.get("published_s") or {}
        if "reserve_base" not in sb or "reserve_base" not in pu:
            n["missing_state"] += 1
            continue
        pool = b.get("pool") or (meta.get(int(b["idx"])) or {}).get("pubkey") if b.get("idx") is not None else None
        hx = b.get("trigger_sig") or b.get("sig")
        tx = cache.get(hx) if hx else None
        idx = b.get("idx")
        pmeta = meta.get(int(idx)) if idx is not None else {}
        pl = {"quote_mint": (pmeta or {}).get("my"), "base_mint": (pmeta or {}).get("mx"),
              "creator_fee_bps": int(sb.get("creator_fee_bps") or 0),
              "coin_creator": "", "canonical": False}
        rb = int(sb.get("base_vault_amount", sb["reserve_base"]))
        rq = int(sb.get("quote_vault_amount", sb["reserve_quote"]))
        s0 = fee_overlay_state(sb, fee_cfg, gcfg, pl if pl.get("quote_mint") else None, 0, rb, rq)
        s0["virtual_quote"] = int(sb.get("virtual_quote_reserves", sb.get("virtual_quote") or 0))
        s0["virtual_quote_reserves"] = s0["virtual_quote"]

        bucket = None
        if tx and pool:
            cpis = cpis_for_pool(tx, pool)
            overlay_n += 1
            if any(c.get("kind") == "buy_exact_out" for c in cpis) and any(c.get("kind") == "sell" for c in cpis):
                sells_two_leg += 1
            if any(c.get("kind") == "unknown" for c in cpis):
                bucket = "unsupported_cpi"
            elif not cpis:
                bucket = "association_ambiguity"
            else:
                term, fail = apply_sequence(s0, cpis)
                bucket = classify_overlay(sb, pu, term, fail, cpis)
                if bucket == "publication_order" and s0.get("virtual_quote") in (0, None):
                    # quote/base miss with V=0 is the 012 hole, not a pub bug
                    if tag in ("explained_virtual", "explained_virtual_fee_residual"):
                        bucket = "missing_state"
        else:
            # no tx bytes: single-CPI using encoded N only if one direction
            d, ain = _dir_amt(b)
            if tag == "wrong_association":
                bucket = "association_ambiguity"
            elif tag == "wrong_n":
                bucket = "missing_state" if not tx else "association_ambiguity"
            elif d is not None and ain:
                g = apply_swap(s0, ain, d)
                if g and g["reserve_base"] == int(pu["reserve_base"]) and g["reserve_quote"] == int(pu["reserve_quote"]):
                    bucket = "bit_exact"
                elif tag in ("explained_virtual", "explained_virtual_fee_residual"):
                    bucket = "missing_state"
                else:
                    bucket = "missing_state"
            else:
                bucket = "missing_state"

        n[bucket] += 1
        if len(examples[bucket]) < 4:
            examples[bucket].append({
                "idx": idx, "old": tag, "pool": pool,
                "n_cpis": len(cpis) if tx and pool else 0,
            })

    doc = {
        "model": MODEL,
        "pump_mismatches": sum(old.values()),
        "overlay_with_tx": overlay_n,
        "two_leg_sell_buyout": sells_two_leg,
        "old_replay": dict(old),
        "residual": {k: n[k] for k in BUCKETS},
        "examples": examples,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PUMP016_OVERLAY.json").write_text(json.dumps(doc, indent=2) + "\n")
    lines = [
        "# PUMP-TX-016 overlay replay",
        "",
        f"model {MODEL}",
        f"Pump mismatches {doc['pump_mismatches']}  overlay-with-tx {overlay_n}  two-leg {sells_two_leg}",
        "",
        "## residuals",
    ]
    for k in BUCKETS:
        lines.append(f"- {k}: {n[k]}")
    lines += ["", "## prior replay tags", ""]
    for k, v in old.most_common():
        lines.append(f"- {k}: {v}")
    md = "\n".join(lines) + "\n"
    (outdir / "PUMP016_OVERLAY.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
