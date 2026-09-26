#!/usr/bin/env python3
"""ALPHA-CENSUS-001 sampler. Read-only RPC. No sends. Does not touch production captures."""
from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\alpha_census")
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WINDOW_S = 45 * 60
SAMPLE_PER = 700
MEV = "https://mev.live/api/arb-explorer/search"
SEARCHERS = {
    "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X": "Mriya",
    "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK": "4BQ",
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "Dtvmxr",
    "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu": "7dGrdJ",
    "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd": "gtagyE",
    "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4": "9EwQoN",
}

# Quote-kernel effect. Grounded in dlmm_quote / pump_quote fields, not in measured edge.
EFFECT = {
    "swap": "PRICE_MOVING",
    "swap2": "PRICE_MOVING",
    "swap_exact_out": "PRICE_MOVING",
    "swap_exact_out2": "PRICE_MOVING",
    "swap_with_price_impact": "PRICE_MOVING",
    "swap_with_price_impact2": "PRICE_MOVING",
    "buy": "PRICE_MOVING",
    "buy_exact_quote_in": "PRICE_MOVING",
    "sell": "PRICE_MOVING",
    "add_liquidity": "DEPTH_MOVING",
    "add_liquidity2": "DEPTH_MOVING",
    "add_liquidity_by_strategy": "DEPTH_MOVING",
    "add_liquidity_by_strategy2": "DEPTH_MOVING",
    "add_liquidity_by_strategy_one_side": "DEPTH_MOVING",
    "add_liquidity_by_weight": "DEPTH_MOVING",
    "add_liquidity_by_weight2": "DEPTH_MOVING",
    "add_liquidity_one_side": "DEPTH_MOVING",
    "add_liquidity_one_side_precise": "DEPTH_MOVING",
    "add_liquidity_one_side_precise2": "DEPTH_MOVING",
    "remove_liquidity": "DEPTH_MOVING",
    "remove_liquidity2": "DEPTH_MOVING",
    "remove_liquidity_by_range": "DEPTH_MOVING",
    "remove_liquidity_by_range2": "DEPTH_MOVING",
    "remove_all_liquidity": "DEPTH_MOVING",
    "rebalance_liquidity": "DEPTH_MOVING",
    "deposit": "DEPTH_MOVING",
    "withdraw": "DEPTH_MOVING",
    "close_position": "DEPTH_MOVING",
    "close_position2": "DEPTH_MOVING",
    "close_position_if_empty": "NON_PRICING",
    "place_limit_order": "DEPTH_MOVING",
    "cancel_limit_order": "DEPTH_MOVING",
    "go_to_a_bin": "PRICE_MOVING",
    "initialize_lb_pair": "ROUTE_CAPACITY_MOVING",
    "initialize_lb_pair2": "ROUTE_CAPACITY_MOVING",
    "initialize_permission_lb_pair": "ROUTE_CAPACITY_MOVING",
    "initialize_customizable_permissionless_lb_pair": "ROUTE_CAPACITY_MOVING",
    "initialize_customizable_permissionless_lb_pair2": "ROUTE_CAPACITY_MOVING",
    "create_pool": "ROUTE_CAPACITY_MOVING",
    "set_pair_status": "ROUTE_CAPACITY_MOVING",
    "set_pair_status_permissionless": "ROUTE_CAPACITY_MOVING",
    "set_activation_point": "ROUTE_CAPACITY_MOVING",
    "disable": "ROUTE_CAPACITY_MOVING",
    "migrate_pool_coin_creator": "NON_PRICING",
    "update_base_fee_parameters": "FEE_MOVING",
    "update_dynamic_fee_parameters": "FEE_MOVING",
    "update_fee_config": "FEE_MOVING",
    "update_creator_fee_config": "FEE_MOVING",
    "claim_fee": "NON_PRICING",
    "claim_fee2": "NON_PRICING",
    "withdraw_protocol_fee": "NON_PRICING",
    "zap_protocol_fee": "NON_PRICING",
    "collect_coin_creator_fee": "NON_PRICING",
    "claim_cashback": "NON_PRICING",
    "initialize_bin_array": "NON_PRICING",
    "initialize_bin_array_bitmap_extension": "NON_PRICING",
    "increase_oracle_length": "NON_PRICING",
    "initialize_position": "NON_PRICING",
    "initialize_position2": "NON_PRICING",
    "update_fees_and_rewards": "NON_PRICING",
    "update_fees_and_reward2": "NON_PRICING",
}


def shyft() -> str:
    for line in (OUT.parents[1] / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("SHYFT_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            return "https://rpc.shyft.to?api_key=" + key
    raise SystemExit("no shyft")


def rpc(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    last = None
    for i in range(6):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode())
            if data.get("error"):
                last = data["error"]
                time.sleep(0.35 * (i + 1))
                continue
            return data.get("result")
        except Exception as e:
            last = e
            time.sleep(0.35 * (i + 1))
    return {"_error": str(last)[:180]}


def family(ix: str) -> str:
    n = ix.lower()
    if n in ("swap", "swap2", "swap_exact_out", "swap_exact_out2", "swap_with_price_impact", "swap_with_price_impact2", "buy", "buy_exact_quote_in", "sell"):
        return "swap"
    if n.startswith("add_liquidity") or n.startswith("remove_") or n in ("rebalance_liquidity", "deposit", "withdraw"):
        return "liquidity"
    if n.startswith("close_position") and "empty" not in n:
        return "liquidity"
    if n.startswith("initialize_lb_pair") or n.startswith("initialize_customizable") or n.startswith("initialize_permission") or n in ("create_pool", "set_activation_point", "set_pair_status", "set_pair_status_permissionless", "disable"):
        return "lifecycle"
    if "fee" in n or n.startswith("claim_") or n.startswith("collect_") or n.startswith("zap_"):
        return "fee_config"
    if n in ("go_to_a_bin",) or n.startswith("initialize_bin") or n.startswith("increase_oracle"):
        return "admin_state"
    if "limit_order" in n:
        return "limit_order"
    return "other"


def bucket(ixs: list[str]) -> str:
    fams = [family(x) for x in ixs]
    if "swap" in fams and "liquidity" in fams:
        return "swap+liquidity"
    if "swap" in fams:
        return "swap"
    if "liquidity" in fams:
        return "liquidity"
    if "lifecycle" in fams:
        return "lifecycle"
    if "fee_config" in fams:
        return "fee_config"
    if "admin_state" in fams:
        return "admin_state"
    if "limit_order" in fams:
        return "limit_order"
    if ixs:
        return "other"
    return "no_program_ix"


def parse_tx(tx: dict, program: str) -> dict:
    if not tx or tx.get("_error"):
        return {"ok": False}
    meta = tx.get("meta") or {}
    if meta.get("err"):
        return {"ok": False, "err": True}
    logs = meta.get("logMessages") or []
    ixs = []
    # Anchor logs the instruction name on the program that is currently executing.
    # Keep names that appear while this program is the top of a simple invoke stack.
    stack = []
    for line in logs:
        if line.startswith("Program ") and line.endswith(" invoke [1]"):
            stack = [line.split()[1]]
        elif line.startswith("Program ") and " invoke [" in line:
            stack.append(line.split()[1])
        elif line.startswith("Program ") and " success" in line and stack:
            stack.pop()
        elif line.startswith("Program log: Instruction: ") and stack and stack[-1] == program:
            ixs.append(line.split("Instruction: ", 1)[1].strip())
    mints = []
    for b in (meta.get("postTokenBalances") or []) + (meta.get("preTokenBalances") or []):
        m = b.get("mint")
        if m and m not in mints:
            mints.append(m)
    slot = tx.get("slot")
    sigs = (tx.get("transaction") or {}).get("signatures") or []
    bt = tx.get("blockTime")
    return {
        "ok": True,
        "slot": slot,
        "blockTime": bt,
        "sig": sigs[0] if sigs else None,
        "ixs": ixs,
        "bucket": bucket(ixs),
        "mints": mints[:6],
        "effects": sorted({EFFECT.get(i, "UNKNOWN") for i in ixs}) or ["UNKNOWN"],
    }


def signatures(url: str, program: str, t_min: int) -> list[dict]:
    out = []
    before = None
    while len(out) < 20000:
        cfg = {"limit": 1000}
        if before:
            cfg["before"] = before
        rows = rpc(url, "getSignaturesForAddress", [program, cfg])
        if not isinstance(rows, list) or not rows:
            break
        stop = False
        for row in rows:
            bt = row.get("blockTime") or 0
            if bt and bt < t_min:
                stop = True
                break
            out.append({"sig": row["signature"], "slot": row.get("slot"), "err": bool(row.get("err")), "bt": bt})
        before = rows[-1]["signature"]
        print(f"  sigs {program[:4]} {len(out)}", flush=True)
        if stop or len(rows) < 1000:
            break
    return out


def fetch_tx(url: str, sig: str) -> dict:
    tx = rpc(url, "getTransaction", [sig, {
        "encoding": "json",
        "maxSupportedTransactionVersion": 1,
        "commitment": "confirmed",
    }])
    if not isinstance(tx, dict):
        return {"_error": "empty"}
    return tx


def mev_window(t0: int, t1: int) -> list[dict]:
    pending = [(t0, t1)]
    leaves = []
    seen = set()
    rows_out = []
    calls = 0
    while pending:
        batch = pending[:6]
        pending = pending[6:]

        def one(span):
            a, b = span
            q = urllib.parse.urlencode({
                "sort_by": "time", "sort_dir": "desc",
                "time_from": a, "time_to": b, "recent_mint_window_secs": 0,
            })
            req = urllib.request.Request(MEV + "?" + q, headers={
                "Referer": "https://mev.live/arbitrages",
                "Origin": "https://mev.live",
                "User-Agent": "arb-research/census",
            })
            with urllib.request.urlopen(req, timeout=40) as r:
                return a, b, json.loads(r.read().decode())

        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(one, s) for s in batch]
            for fut in as_completed(futs):
                a, b, resp = fut.result()
                calls += 1
                got = resp.get("rows") or []
                total = int(resp.get("total_count") or 0)
                if total == 0:
                    continue
                if len(got) >= total or (b - a) <= 8:
                    leaves.append(got)
                else:
                    mid = (a + b) // 2
                    pending.append((a, mid))
                    pending.append((mid, b))
        if calls % 40 == 0:
            print(f"  mev calls={calls} pending={len(pending)}", flush=True)
    for got in leaves:
        for r in got:
            sig = r.get("signature")
            if not sig or sig in seen:
                continue
            seen.add(sig)
            rows_out.append(r)
    print(f"mev rows {len(rows_out)} calls {calls}", flush=True)
    return rows_out


def main() -> int:
    url = shyft()
    now = int(rpc(url, "getSlot", []) and time.time())
    # block time from a recent slot via getBlockTime
    slot = rpc(url, "getSlot", [])
    now_bt = int(rpc(url, "getBlockTime", [slot]) or time.time())
    t_min = now_bt - WINDOW_S
    print(f"window {t_min}..{now_bt}", flush=True)
    sigs = {}
    for prog, name in ((DLMM, "dlmm"), (PUMP, "pump")):
        print("paging", name, flush=True)
        sigs[name] = signatures(url, prog, t_min)
        (OUT / f"sigs_{name}.json").write_text(json.dumps(sigs[name]), encoding="utf-8")
    random.seed(11)
    parsed = []
    for name, prog in (("dlmm", DLMM), ("pump", PUMP)):
        pool = [s for s in sigs[name] if not s["err"]]
        random.shuffle(pool)
        take = pool[:SAMPLE_PER]
        print(f"fetch {name} {len(take)} of {len(pool)}", flush=True)
        done = 0
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(fetch_tx, url, s["sig"]): s for s in take}
            for fut in as_completed(futs):
                meta = futs[fut]
                tx = fut.result()
                rec = parse_tx(tx, prog)
                rec["program"] = name
                rec["sig"] = meta["sig"]
                rec["sig_slot"] = meta["slot"]
                rec["sig_bt"] = meta["bt"]
                parsed.append(rec)
                done += 1
                if done % 100 == 0:
                    print(f"  {name} {done}", flush=True)
    (OUT / "sample.jsonl").write_text("".join(json.dumps(r) + "\n" for r in parsed), encoding="utf-8")
    bts = [r["sig_bt"] for r in parsed if r.get("sig_bt")]
    t0, t1 = (min(bts), max(bts)) if bts else (t_min, now_bt)
    print(f"mev {t0}..{t1}", flush=True)
    arbs = mev_window(t0, t1)
    (OUT / "mev_window.jsonl").write_text(
        "".join(json.dumps({
            "sig": r.get("signature"), "slot": r.get("slot"), "time": r.get("time"),
            "user": r.get("user"), "usd": r.get("pure_profit"), "dexes": r.get("dexes"),
            "mint": r.get("two_leg_arb_mint"), "hops": r.get("number_of_swap_steps"),
        }) + "\n" for r in arbs),
        encoding="utf-8",
    )
    by_mint = defaultdict(list)
    for r in arbs:
        if r.get("two_leg_arb_mint") and r.get("slot"):
            by_mint[r["two_leg_arb_mint"]].append(r)
    for m in by_mint:
        by_mint[m].sort(key=lambda r: int(r["slot"]))

    def follow(rec):
        slot = rec.get("sig_slot") or 0
        hits = []
        for m in rec.get("mints") or []:
            for a in by_mint.get(m, []):
                ds = int(a["slot"]) - int(slot)
                if 0 <= ds <= 5:
                    hits.append(a)
        hits.sort(key=lambda a: int(a["slot"]))
        return hits

    summary = {
        "window": [t0, t1],
        "sig_counts": {k: {"n": len(v), "err": sum(1 for s in v if s["err"])} for k, v in sigs.items()},
        "sample_n": len(parsed),
        "mev_n": len(arbs),
        "mev_usd": sum(float(r.get("pure_profit") or 0) for r in arbs),
    }
    rows_out = []
    for rec in parsed:
        if not rec.get("ok"):
            continue
        hits = follow(rec)
        elite = sorted({SEARCHERS[h["user"]] for h in hits if h.get("user") in SEARCHERS})
        taker = "NO_MEV_LIVE_MINT_MATCH"
        if hits:
            taker = "CAPTURED_KNOWN_ARB" if elite else "CAPTURED_UNKNOWN_OR_UNLABELED"
        rec2 = {
            "signature": rec["sig"],
            "slot": rec.get("sig_slot"),
            "program": rec["program"],
            "trigger_class": rec["bucket"],
            "instructions": rec["ixs"],
            "effects": rec["effects"],
            "mints": rec["mints"],
            "taker": taker,
            "elite": elite,
            "slots_to_taker": (int(hits[0]["slot"]) - int(rec["sig_slot"])) if hits else None,
            "taker_usd": float(hits[0].get("pure_profit") or 0) if hits else None,
            "state_confidence": "STATE_UNAVAILABLE",
            "edge_before": None,
            "edge_after": None,
            "preexec": "UNKNOWN",
        }
        rows_out.append(rec2)
    (OUT / "joined.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows_out), encoding="utf-8")
    # rates
    def rates(rows):
        acc = {}
        for r in rows:
            k = (r["program"], r["trigger_class"])
            a = acc.setdefault(k, {"n": 0, "taker": 0, "elite": 0, "ix": Counter()})
            a["n"] += 1
            if r["taker"] != "NO_MEV_LIVE_MINT_MATCH":
                a["taker"] += 1
            if r["elite"]:
                a["elite"] += 1
            for ix in r["instructions"]:
                a["ix"][ix] += 1
        return acc
    acc = rates(rows_out)
    table = []
    for (prog, cls), a in sorted(acc.items(), key=lambda kv: -kv[1]["n"]):
        table.append({
            "program": prog,
            "class": cls,
            "n": a["n"],
            "taker_n": a["taker"],
            "taker_pct": round(100 * a["taker"] / a["n"], 1) if a["n"] else None,
            "elite_n": a["elite"],
            "elite_pct": round(100 * a["elite"] / a["n"], 1) if a["n"] else None,
            "top_ix": a["ix"].most_common(6),
        })
    summary["table"] = table
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(table, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
