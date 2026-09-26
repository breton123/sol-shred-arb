#!/usr/bin/env python3
"""PUMP-FEE-015 reducer. Frozen soak. Fetches FeeConfig + GlobalConfig.

Replay all 1003 buy_exact_quote_in residuals with schedule fees.
For cached fee014 txs, compare predicted recipient credits to transfers.
Does not deploy.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from collections import Counter, defaultdict  # noqa: F401
from pathlib import Path

from pump_fee import (
    FEE_CONFIG_PK,
    PUMP_AMM,
    WSOL,
    buy_components,
    parse_fee_config,
    parse_global_config,
    parse_pool_meta,
    resolve_fee_state,
    role_owner,
)
from reduce_buy013 import collect, pred_buy_quote
from reduce_fee014 import quote_deltas, rpc
from replay import _dir_amt

MODES = ("ignore", "carve")
GATES = ("isPumpPool", "coin_creator", "virtual", "sol_quote")
NONCANON = ("flat", "global")


def fetch_b64(url: str, pks: list[str]) -> dict[str, bytes]:
    out = {}
    for i in range(0, len(pks), 80):
        chunk = pks[i:i + 80]
        vals = rpc(url, "getMultipleAccounts", [chunk, {"encoding": "base64"}])
        if not vals:
            continue
        for pk, acc in zip(chunk, vals.get("value") or []):
            if not acc:
                continue
            out[pk] = base64.b64decode(acc["data"][0])
    return out


def mint_supply(url: str, pks: list[str]) -> dict[str, int]:
    out = {}
    for i in range(0, len(pks), 80):
        chunk = pks[i:i + 80]
        vals = rpc(url, "getMultipleAccounts", [chunk, {"encoding": "jsonParsed"}])
        if not vals:
            continue
        for pk, acc in zip(chunk, vals.get("value") or []):
            if not acc:
                continue
            info = ((acc.get("data") or {}).get("parsed") or {}).get("info") or {}
            try:
                out[pk] = int(info.get("supply") or 0)
            except (TypeError, ValueError):
                out[pk] = 0
    return out


def ata_owners(url: str, pks: list[str]) -> dict[str, str]:
    out = {}
    for i in range(0, len(pks), 80):
        chunk = pks[i:i + 80]
        vals = rpc(url, "getMultipleAccounts", [chunk, {"encoding": "jsonParsed"}])
        if not vals:
            continue
        for pk, acc in zip(chunk, vals.get("value") or []):
            if not acc:
                continue
            info = ((acc.get("data") or {}).get("parsed") or {}).get("info") or {}
            own = info.get("owner")
            if own:
                out[pk] = own
    return out


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/data/bsc/captures/soak_fastsoak_20260925/state008")
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent
    url = os.environ.get("HELIUS_RPC_URL") or os.environ.get("RPC_URL")
    if not url:
        print("need HELIUS_RPC_URL", file=sys.stderr)
        return 2

    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    meta = {int(p["idx"]): p for p in u.get("pools") or []}
    buys, cleans = collect(root / "mismatch", meta)

    gcfg_pk = None
    # GlobalConfig PDA seeds ["global_config"] on Pump AMM
    from pump_fee import find_pda, b58decode, b58encode
    gcfg_pk = b58encode(find_pda([b"global_config"], b58decode(PUMP_AMM)))

    accs = fetch_b64(url, [FEE_CONFIG_PK, gcfg_pk])
    fee_cfg = parse_fee_config(accs[FEE_CONFIG_PK])
    gcfg = parse_global_config(accs[gcfg_pk])

    pool_pks = sorted({(meta.get(int(b["idx"])) or {}).get("pubkey") for b in buys} - {None})
    pool_raw = fetch_b64(url, pool_pks)
    pools = {pk: parse_pool_meta(raw) for pk, raw in pool_raw.items()}
    bases = sorted({p["base_mint"] for p in pools.values() if p.get("base_mint")})
    supplies = mint_supply(url, bases)

    cfg_dump = {
        "fee_config_pk": FEE_CONFIG_PK,
        "global_config_pk": gcfg_pk,
        "fee_config": {k: v for k, v in fee_cfg.items() if k != "admin"},
        "global": {
            "lp_fee_bps": gcfg["lp_fee_bps"],
            "protocol_fee_bps": gcfg["protocol_fee_bps"],
            "coin_creator_fee_bps": gcfg["coin_creator_fee_bps"],
            "buyback_basis_points": gcfg["buyback_basis_points"],
            "creator_fee_configurable": gcfg["creator_fee_configurable"],
            "mayhem_mode_enabled": gcfg["mayhem_mode_enabled"],
            "is_cashback_enabled": gcfg["is_cashback_enabled"],
            "protocol_fee_recipients": gcfg["protocol_fee_recipients"],
            "buyback_fee_recipients": gcfg["buyback_fee_recipients"],
            "reserved_fee_recipient": gcfg["reserved_fee_recipient"],
            "reserved_fee_recipients": gcfg["reserved_fee_recipients"],
        },
        "n_fee_tiers": len(fee_cfg["fee_tiers"]),
        "n_stable_tiers": len(fee_cfg["stable_fee_tiers"]),
        "flat_fees": fee_cfg["flat_fees"],
        "exotic_flat_fees": fee_cfg["exotic_flat_fees"],
        "tier_thresholds": [t["market_cap_lamports_threshold"] for t in fee_cfg["fee_tiers"]],
        "tier_fees": [t["fees"] for t in fee_cfg["fee_tiers"]],
    }

    vault_hits = {f"{g}|{nc}|{mode}": 0 for g in GATES for nc in NONCANON for mode in MODES}
    remain = Counter()
    unexplained_n = 0
    examples = []
    canon_n = Counter()
    cr_src_n = Counter()
    # preferred: documented gate + global fallback (AUTH lp/proto)
    PREF = ("coin_creator", "global", "carve")

    for b in buys:
        idx = int(b["idx"])
        pmeta = meta.get(idx) or {}
        pk = pmeta.get("pubkey")
        pl = pools.get(pk) or {}
        sb = b["s_before"]
        pu = b["published_s"]
        _, ain = _dir_amt(b)
        pub = int(pu["reserve_quote"]) - int(sb["reserve_quote"])
        rb = int(sb.get("base_vault_amount", sb["reserve_base"]))
        rq = int(sb.get("quote_vault_amount", sb["reserve_quote"]))
        if not pl.get("quote_mint"):
            pl = dict(pl)
            pl["quote_mint"] = pmeta.get("my") or pmeta.get("mx") or WSOL
            pl["base_mint"] = pl.get("base_mint") or pmeta.get("mx")
            pl["creator_fee_bps"] = int(pl.get("creator_fee_bps") or 0)
        supply = supplies.get(pl.get("base_mint") or "", 0)
        hit_pref = False
        for gate in GATES:
            for nc in NONCANON:
                st = resolve_fee_state(
                    fee_cfg, gcfg, pl, supply, rb, rq, quote_for_mc=rq,
                    gate=gate, noncanon=nc,
                )
                if gate == "isPumpPool" and nc == "flat":
                    canon_n[st["canonical"]] += 1
                    cr_src_n[st["creator_source"]] += 1
                for mode in MODES:
                    c = buy_components(
                        ain, st["lp_fee_bps"], st["protocol_fee_bps"],
                        st["creator_fee_bps"], st["buyback_bps"], mode,
                    )
                    if not c.get("ok"):
                        continue
                    key = f"{gate}|{nc}|{mode}"
                    if c["vault"] == pub:
                        vault_hits[key] += 1
                        if (gate, nc, mode) == PREF:
                            hit_pref = True
        if not hit_pref:
            unexplained_n += 1
            remain[idx] += 1
            if len(examples) < 8:
                st = resolve_fee_state(
                    fee_cfg, gcfg, pl, supply, rb, rq, gate=PREF[0], noncanon=PREF[1],
                )
                c = buy_components(
                    ain, st["lp_fee_bps"], st["protocol_fee_bps"],
                    st["creator_fee_bps"], st["buyback_bps"], PREF[2],
                )
                _, old = pred_buy_quote(sb, ain)
                examples.append({
                    "idx": idx, "ain": ain, "pub": pub,
                    "old_pred": ain - old["proto"] - old["creator"],
                    "state": {k: st[k] for k in (
                        "canonical", "use_tiers", "fee_src", "market_cap",
                        "lp_fee_bps", "protocol_fee_bps", "creator_fee_bps",
                        "creator_source", "buyback_bps", "quote_class",
                    )},
                    "comp": c,
                    "pool_cr": pl.get("creator_fee_bps"),
                    "coin_creator": (pl.get("coin_creator") or "")[:8],
                    "virt": pl.get("virtual_quote_reserves"),
                    "supply": supply,
                })

    # transfer conservation vs predicted components on cached txs
    by_sig = {}
    for b in buys:
        hx = b.get("trigger_sig") or b.get("sig")
        if hx:
            by_sig[hx] = b
    txdir = root.parent / "fee014_tx"
    transfer_n = 0
    xfer_match = Counter()
    role_n = Counter()
    role_amt = defaultdict(int)
    triple_roles = Counter()
    owners_need = []
    xfer_examples = []

    parsed_cache = []
    for fp in txdir.glob("*.json") if txdir.is_dir() else []:
        hx = fp.stem
        b = by_sig.get(hx)
        if not b:
            continue
        idx = int(b["idx"])
        pmeta = meta.get(idx) or {}
        qmint = pmeta.get("my") or pmeta.get("mx") or WSOL
        vault = None
        for w in b.get("staged_writes") or []:
            if w.get("role") == "pump_vault_quote":
                vault = w.get("pubkey")
                break
        vault = vault or pmeta.get("vy") or pmeta.get("vault_y")
        tx = json.loads(fp.read_text())
        d = quote_deltas(tx, qmint)
        if not d:
            continue
        credits = [(pk, am) for pk, am in d.items() if am > 0]
        owners_need.extend(pk for pk, _ in credits)
        parsed_cache.append((hx, b, pmeta, vault, d, credits))

    owners = ata_owners(url, sorted(set(owners_need))) if owners_need else {}

    for hx, b, pmeta, vault, d, credits in parsed_cache:
        idx = int(b["idx"])
        pk = pmeta.get("pubkey")
        pl = pools.get(pk) or {}
        sb = b["s_before"]
        _, ain = _dir_amt(b)
        rb = int(sb.get("base_vault_amount", sb["reserve_base"]))
        rq = int(sb.get("quote_vault_amount", sb["reserve_quote"]))
        vq = int(sb.get("virtual_quote_reserves", sb.get("virtual_quote") or 0))
        supply = supplies.get(pl.get("base_mint") or "", 0)
        if not pl.get("quote_mint"):
            pl = dict(pl)
            pl["quote_mint"] = pmeta.get("my") or WSOL
        st = resolve_fee_state(
            fee_cfg, gcfg, pl, supply, rb, rq, quote_for_mc=rq,
            gate=PREF[0], noncanon=PREF[1],
        )
        c = buy_components(
            ain, st["lp_fee_bps"], st["protocol_fee_bps"],
            st["creator_fee_bps"], st["buyback_bps"], PREF[2],
        )
        roles = []
        pred = {
            "protocol": c.get("protocol"),
            "creator": c.get("creator"),
            "buyback": c.get("buyback"),
            "vault": c.get("vault"),
        }
        got = {"protocol": 0, "creator": 0, "buyback": 0, "reserved": 0, "vault": 0, "other": 0}
        for acc, am in credits:
            if vault and acc == vault:
                got["vault"] += am
                role = "pool_quote_vault"
            else:
                own = owners.get(acc)
                role = role_owner(own, gcfg) if own else "other"
                if role == "protocol_fee_recipient":
                    got["protocol"] += am
                elif role == "buyback_fee_recipient":
                    got["buyback"] += am
                elif role == "reserved_fee_recipient":
                    got["reserved"] += am
                else:
                    got["other"] += am
            roles.append(role)
            role_n[role] += 1
            role_amt[role] += am
        transfer_n += 1
        triple_roles[tuple(sorted(roles))] += 1
        # bit-exact: vault + protocol + creator(+buyback/reserved as creator dump)
        if got["vault"] == pred["vault"]:
            xfer_match["vault"] += 1
        if got["vault"] == pred["vault"] and got["protocol"] == pred["protocol"] and got["buyback"] == pred["buyback"]:
            xfer_match["vault+proto+buyback"] += 1
        if (got["vault"] == pred["vault"]
                and got["protocol"] == pred["protocol"]
                and got["buyback"] == pred["buyback"]
                and got["other"] + got["reserved"] == pred["creator"]):
            xfer_match["all_four"] += 1
        if got["vault"] + got["protocol"] + got["buyback"] + got["reserved"] + got["other"] == ain:
            xfer_match["conservation"] += 1
        if len(xfer_examples) < 6:
            xfer_examples.append({
                "idx": idx, "ain": ain, "pred": pred, "got": got, "roles": roles,
                "bps": {k: st[k] for k in ("lp_fee_bps", "protocol_fee_bps", "creator_fee_bps", "buyback_bps", "canonical", "market_cap")},
            })

    sell_ok = 0
    for b in cleans:
        d, ain = _dir_amt(b)
        if d != 1:
            continue
        sell_ok += 1  # 013 already 0-fail; count only

    doc = {
        "n_buy": len(buys),
        "n_clean": len(cleans),
        "config": cfg_dump,
        "canonical_counts": dict(canon_n),
        "creator_source": dict(cr_src_n),
        "vault_bitexact": vault_hits,
        "preferred": "|".join(PREF),
        "preferred_hits": vault_hits.get("|".join(PREF), 0),
        "best_vault": max(vault_hits, key=vault_hits.get) if vault_hits else None,
        "unexplained_by_idx_top": remain.most_common(16),
        "n_unexplained_pref": unexplained_n,
        "transfer_n": transfer_n,
        "transfer_match": dict(xfer_match),
        "credit_roles": dict(role_n),
        "credit_role_amt": dict(role_amt),
        "role_sets": [[list(k), v] for k, v in triple_roles.most_common(8)],
        "examples": examples,
        "xfer_examples": xfer_examples,
        "sell_clean_n": sell_ok,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PUMP015_FEE.json").write_text(json.dumps(doc, indent=2, default=str) + "\n")
    best = doc["best_vault"]
    lines = [
        "# PUMP-FEE-015 reducer",
        "",
        f"buy residuals: {len(buys)}  clean virtual: {len(cleans)}",
        f"FeeConfig tiers: {cfg_dump['n_fee_tiers']}  stable: {cfg_dump['n_stable_tiers']}",
        f"flat={cfg_dump['flat_fees']}  buyback_bps={gcfg['buyback_basis_points']}  creator_configurable={gcfg['creator_fee_configurable']}",
        "",
        "## vault bit-exact (schedule fees, not fitted bps)",
    ]
    for k, v in sorted(vault_hits.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}/{len(buys)}")
    lines += [
        "",
        f"best {best} = {vault_hits.get(best, 0)}/{len(buys)}",
        f"preferred {'|'.join(PREF)} unexplained {doc['n_unexplained_pref']}",
        "",
        "## transfer roles on cached txs",
        f"n={transfer_n} match={dict(xfer_match)}",
        f"roles={dict(role_n)}",
    ]
    md = "\n".join(lines) + "\n"
    (outdir / "PUMP015_FEE.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
