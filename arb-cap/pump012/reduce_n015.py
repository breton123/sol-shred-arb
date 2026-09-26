#!/usr/bin/env python3
"""PUMP-N-015 — classify the 168 wrong-N sells. No deploy.

Sell identity: published base vault = before + executed_base_in.
If encoded amount_in ≠ that delta, N is wrong. Split by *how* the
encoded number relates to the executed delta and the tx transfers.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from pump_apply import apply_swap
from pump_fee import B58, b58decode_any, b58encode, flatten_keys
from reduce_fee014 import quote_deltas, rpc
from replay import _dir_amt, replay_one

N_LITERAL = "N_LITERAL"
N_BALANCE_DERIVED = "N_BALANCE_DERIVED"
N_PREVIOUS_OUTPUT = "N_PREVIOUS_OUTPUT"
N_INVERSE_QUOTE = "N_INVERSE_QUOTE"
N_CLAMPED = "N_CLAMPED"
N_UNKNOWN = "N_UNKNOWN"

PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
SELL = bytes.fromhex("33e685a4017f83ad")
BUY_EQ = bytes.fromhex("c62e1552b4d9e870")
BUY_OUT = bytes.fromhex("66063d1201daebea")  # buy exact-out if present


def sig_b58(b: dict) -> str | None:
    hx = b.get("trigger_sig") or b.get("sig") or b.get("sig_hex")
    if not hx:
        for w in b.get("staged_writes") or []:
            if w.get("txn_sig"):
                hx = w["txn_sig"]
                break
    if not hx or not isinstance(hx, str):
        return None
    if len(hx) == 128 and all(c in "0123456789abcdefABCDEF" for c in hx):
        return b58encode(bytes.fromhex(hx))
    return hx


def collect_wrong_n(misdir: Path) -> list[dict]:
    out = []
    for p in misdir.glob("*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if b.get("kind") != "pump":
            continue
        if replay_one(b) == "wrong_n":
            b["_file"] = p.name
            out.append(b)
    return out


def collect_assoc(misdir: Path) -> list[dict]:
    out = []
    for p in misdir.glob("*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if b.get("kind") != "pump":
            continue
        if replay_one(b) == "wrong_association":
            b["_file"] = p.name
            out.append(b)
    return out


def executed_n(b: dict) -> int | None:
    d, ain = _dir_amt(b)
    sb, pu = b["s_before"], b["published_s"]
    brb = int(sb["reserve_base"])
    urb = int(pu["reserve_base"])
    if d == 1:
        return urb - brb
    if d == 0:
        return brb - urb
    return None


def mint_deltas(tx: dict, mint: str) -> dict[str, int]:
    return quote_deltas(tx, mint)


def pump_legs(tx: dict, keys: list[str]) -> list[dict]:
    """Every Pump AMM ix (outer + inner) with decoded amount and pool."""
    out = []

    def walk(ixs, where, outer_i=None):
        for i, ix in enumerate(ixs or []):
            prog = ix.get("programId")
            if prog is None and isinstance(ix.get("programIdIndex"), int):
                pi = ix["programIdIndex"]
                prog = keys[pi] if pi < len(keys) else ""
            if prog != PUMP:
                continue
            data = ix.get("data") or ""
            raw = b""
            if isinstance(data, str) and data:
                try:
                    raw = b58decode_any(data)
                except Exception:
                    raw = b""
                if len(raw) < 8:
                    try:
                        import base64
                        raw = base64.b64decode(data)
                    except Exception:
                        pass
            elif isinstance(data, (bytes, bytearray)):
                raw = bytes(data)
            accs = []
            if isinstance(ix.get("accounts"), list) and ix["accounts"] and isinstance(ix["accounts"][0], str):
                accs = list(ix["accounts"])
            else:
                for ai in ix.get("accounts") or []:
                    if isinstance(ai, int) and ai < len(keys):
                        accs.append(keys[ai])
            disc = raw[:8] if len(raw) >= 8 else b""
            ain = int.from_bytes(raw[8:16], "little") if len(raw) >= 16 else None
            mino = int.from_bytes(raw[16:24], "little") if len(raw) >= 24 else None
            kind = {SELL: "sell", BUY_EQ: "buy_exact_quote_in", BUY_OUT: "buy_exact_out"}.get(disc)
            if kind is None:
                continue
            out.append({
                "where": where,
                "ix_index": outer_i if where == "inner" else i,
                "inner_ordinal": i if where == "inner" else None,
                "disc": disc.hex(),
                "kind": kind,
                "amount_in": ain,
                "min_out": mino,
                "pool": accs[0] if accs else None,
                "n_acc": len(accs),
                "user": accs[1] if len(accs) > 1 else None,
                "user_base": accs[5] if len(accs) > 5 else None,
                "user_quote": accs[6] if len(accs) > 6 else None,
                "vault_base": accs[7] if len(accs) > 7 else None,
                "vault_quote": accs[8] if len(accs) > 8 else None,
            })

    msg = (tx.get("transaction") or {}).get("message") or {}
    walk(msg.get("instructions") or [], "outer")
    for g in (tx.get("meta") or {}).get("innerInstructions") or []:
        walk(g.get("instructions") or [], "inner", g.get("index"))
    return out


def inverse_sell_base(sb: dict, want_rq: int) -> int | None:
    """Invert sell amount_in from published quote vault (fees on gross)."""
    # after_rq = rq - (gross - lp); gross = qeff * ain / (rb + ain)
    # search ain
    lo, hi = 1, 10**18
    ans = None
    while lo <= hi:
        mid = (lo + hi) // 2
        g = apply_swap(sb, mid, 1)
        if g is None:
            hi = mid - 1
            continue
        got = g["reserve_quote"]
        if got == want_rq:
            return mid
        if got > want_rq:
            lo = mid + 1
        else:
            hi = mid - 1
    return ans


def classify_n(b: dict, tx: dict | None, meta: dict) -> dict:
    d, ain = _dir_amt(b)
    n_exec = executed_n(b)
    sb, pu = b["s_before"], b["published_s"]
    idx = b.get("idx")
    p = meta.get(int(idx)) if idx is not None else {}
    base_mint = (p or {}).get("mx")
    quote_mint = (p or {}).get("my")
    pool = b.get("pool") or (p or {}).get("pubkey")
    row = {
        "idx": idx,
        "pool": pool,
        "dir": d,
        "n_pred": ain,
        "n_exec": n_exec,
        "ratio": round(ain / n_exec, 6) if n_exec else None,
        "class": N_UNKNOWN,
        "rule": None,
        "n_pump_legs": 0,
        "matching_legs": 0,
    }
    if n_exec is None or ain is None:
        return row
    urb, urq = int(pu["reserve_base"]), int(pu["reserve_quote"])
    dq = urq - int(sb["reserve_quote"])
    row["dq"] = dq

    legs = []
    if tx:
        keys = flatten_keys(tx)
        legs = [lg for lg in pump_legs(tx, keys) if lg.get("pool") == pool]
        row["n_pump_legs"] = len(legs)
        row["matching_legs"] = sum(1 for lg in legs if lg.get("amount_in") == ain)
        row["leg_kinds"] = [lg["kind"] for lg in legs]
        row["leg_ains"] = [lg.get("amount_in") for lg in legs]

    if ain == n_exec:
        row["class"] = N_LITERAL
        row["rule"] = "encoded==executed"
        return row

    sell_ains = [lg.get("amount_in") for lg in legs if lg.get("kind") == "sell" and lg.get("amount_in")]
    buy_out_ains = [lg.get("amount_in") for lg in legs if lg.get("kind") == "buy_exact_out" and lg.get("amount_in")]
    if sell_ains and buy_out_ains:
        for s in sell_ains:
            for bo in buy_out_ains:
                if n_exec == s - bo or n_exec == bo - s:
                    row["class"] = N_PREVIOUS_OUTPUT
                    row["rule"] = "same-pool sell + buy_exact_out; published base is net; predicted used one leg"
                    row["n_sell_ix"] = s
                    row["n_buy_out_ix"] = bo
                    return row
    if n_exec is not None and n_exec <= 0:
        row["class"] = N_UNKNOWN
        row["rule"] = "published base did not increase; sell amount_in does not apply (dir/assoc)"
        return row
    if d == 1:
        inv = inverse_sell_base(sb, urq)
        row["n_inverse_quote"] = inv
        if inv == n_exec and ain != n_exec:
            row["class"] = N_INVERSE_QUOTE
            row["rule"] = "n_exec inverted from published quote vault; encoded ≠ exec"
            return row
        if ain == abs(dq) and ain != n_exec:
            row["class"] = N_PREVIOUS_OUTPUT
            row["rule"] = "encoded amount_in equals |quote vault delta| (wrong field / prev-leg quote)"
            return row
    if 0 < n_exec < ain:
        g_exec = apply_swap({**sb, "virtual_quote": sb.get("virtual_quote") or 0}, n_exec, d)
        if g_exec and g_exec["reserve_base"] == urb:
            if not sell_ains or ain in sell_ains:
                row["class"] = N_CLAMPED
                row["rule"] = "sell ix requested N; executed = published base vault delta (< requested)"
                return row
            row["class"] = N_CLAMPED
            row["rule"] = "n_exec=vault_base_delta; encoded > executed (ix amount not recovered)"
            return row

    if tx:
        if any(lg.get("amount_in") == n_exec for lg in legs):
            row["class"] = N_LITERAL
            row["rule"] = "executed equals a Pump-leg amount_in; predicted picked a different leg"
            return row
        if base_mint:
            bd = mint_deltas(tx, base_mint)
            user_debits = sorted((-am for am in bd.values() if am < 0), reverse=True)
            vault_credit = None
            for w in b.get("staged_writes") or []:
                if w.get("role") == "pump_vault_base":
                    vault_credit = bd.get(w.get("pubkey"))
            if vault_credit == n_exec:
                pass
            if n_exec in user_debits:
                if ain in user_debits and ain != n_exec:
                    row["class"] = N_PREVIOUS_OUTPUT
                    row["rule"] = "encoded is another base debit in the same tx; exec is the vault credit"
                    return row
                row["class"] = N_BALANCE_DERIVED
                row["rule"] = "n_exec equals a user base debit (source-balance / ATA delta)"
                return row
            # clamp to source: encoded > user debit == exec
            if user_debits and n_exec == user_debits[0] and ain > n_exec:
                row["class"] = N_CLAMPED
                row["rule"] = "encoded requested; executed = source ATA debit"
                return row
        if quote_mint and d == 1:
            qd = mint_deltas(tx, quote_mint)
            inv = inverse_sell_base(sb, int(pu["reserve_quote"]))
            if inv == n_exec:
                row["class"] = N_INVERSE_QUOTE
                row["rule"] = "n_exec inverted from published quote vault"
                return row
            # previous-leg: encoded == some quote credit/debit
            qabs = [abs(am) for am in qd.values()]
            if ain in qabs and n_exec not in qabs:
                row["class"] = N_PREVIOUS_OUTPUT
                row["rule"] = "encoded equals a quote transfer (router/prev-leg), not base in"
                return row
        if len(legs) > 1:
            row["class"] = N_PREVIOUS_OUTPUT
            row["rule"] = "multi Pump CPI; encoded amount is not this pool's executed base"
            return row

    # ratio clusters without tx
    if row["ratio"] and abs(row["ratio"] - 1) < 1e-9:
        row["class"] = N_LITERAL
        return row
    return row


def classify_assoc(b: dict, tx: dict | None, meta: dict) -> dict:
    idx = b.get("idx")
    p = meta.get(int(idx)) if idx is not None else {}
    pool = b.get("pool") or (p or {}).get("pubkey")
    d, ain = _dir_amt(b)
    row = {
        "idx": idx, "pool": pool, "dir": d, "n_pred": ain,
        "pub_eq_before": False, "n_pump_on_pool": 0, "n_pump_tx": 0,
        "class": "ASSOC_UNKNOWN",
    }
    sb, pu = b.get("s_before") or {}, b.get("published_s") or {}
    try:
        same = (int(sb["reserve_base"]) == int(pu["reserve_base"])
                and int(sb["reserve_quote"]) == int(pu["reserve_quote"]))
    except (KeyError, TypeError, ValueError):
        same = False
    if same:
        row["pub_eq_before"] = True
        row["class"] = "ASSOC_NO_VAULT_MOVE"
    if not tx:
        return row
    keys = flatten_keys(tx)
    legs = pump_legs(tx, keys)
    row["n_pump_tx"] = len(legs)
    on = [lg for lg in legs if lg.get("pool") == pool]
    row["n_pump_on_pool"] = len(on)
    row["leg_ix"] = [(lg["where"], lg["ix_index"], lg["inner_ordinal"], lg["kind"], lg.get("amount_in")) for lg in legs]
    if len(on) == 0 and legs:
        row["class"] = "ASSOC_WRONG_POOL"
        row["rule"] = "predicted pool is not a Pump ix pool in this tx"
    elif len(on) > 1:
        row["class"] = "ASSOC_MULTI_LEG"
        row["rule"] = "multiple Pump CPIs on the same pool; need ix+ordinal"
    elif len(on) == 1 and row["class"] == "ASSOC_NO_VAULT_MOVE":
        row["class"] = "ASSOC_STALE_OR_OTHER_WRITE"
        row["rule"] = "one Pump leg on pool but published vaults == before"
    elif len(legs) > 1 and len(on) == 1:
        row["class"] = "ASSOC_MULTI_POOL_TX"
        row["rule"] = "tx has several Pump pools; this pool has one leg"
    elif len(on) == 1 and not row["pub_eq_before"]:
        row["class"] = "ASSOC_SINGLE_LEG"
        row["rule"] = "one Pump CPI on this pool and vaults moved; anchor by ix+ordinal not sig+pool"
    return row


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/data/bsc/captures/soak_fastsoak_20260925/state008")
    outdir = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent
    url = os.environ.get("HELIUS_RPC_URL") or os.environ.get("RPC_URL")
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    meta = {int(p["idx"]): p for p in u.get("pools") or []}
    wrong = collect_wrong_n(root / "mismatch")
    assoc = collect_assoc(root / "mismatch")

    txdir = root.parent / "n015_tx"
    txdir.mkdir(parents=True, exist_ok=True)
    by_sig = {}
    for b in wrong + assoc:
        hx = b.get("trigger_sig") or b.get("sig") or b.get("sig_hex")
        b58 = sig_b58(b)
        if hx:
            by_sig.setdefault(hx, {"b58": b58, "rows": []})["rows"].append(b)

    fetched = 0
    if url:
        for hx, rec in list(by_sig.items())[:240]:
            fp = txdir / f"{hx}.json"
            if fp.exists():
                continue
            if not rec["b58"]:
                continue
            tx = rpc(url, "getTransaction", [rec["b58"], {"encoding": "json", "maxSupportedTransactionVersion": 1}])
            if tx:
                fp.write_text(json.dumps(tx))
                fetched += 1

    cache = {fp.stem: json.loads(fp.read_text()) for fp in txdir.glob("*.json")}

    n_rows = []
    ncls = Counter()
    ratios = Counter()
    dirs = Counter()
    for b in wrong:
        hx = b.get("trigger_sig") or b.get("sig") or b.get("sig_hex")
        r = classify_n(b, cache.get(hx), meta)
        n_rows.append(r)
        ncls[r["class"]] += 1
        dirs[r["dir"]] += 1
        if r.get("ratio") is not None:
            ratios[round(r["ratio"], 2)] += 1

    # held-out: last 40 rows must obey frozen rule of their class
    hold = n_rows[-40:] if len(n_rows) >= 80 else n_rows[len(n_rows)//2:]
    hold_ok = sum(1 for r in hold if r["class"] != N_UNKNOWN)
    train = n_rows[:len(n_rows) - len(hold)]

    a_rows = []
    acls = Counter()
    for b in assoc:
        hx = b.get("trigger_sig") or b.get("sig") or b.get("sig_hex")
        r = classify_assoc(b, cache.get(hx), meta)
        a_rows.append(r)
        acls[r["class"]] += 1

    # sell regression: 2537 class still explained
    from reduce_buy013 import collect
    _, cleans = collect(root / "mismatch", meta)

    doc = {
        "n_wrong_n": len(wrong),
        "n_assoc": len(assoc),
        "fetched_tx": fetched,
        "cached_tx": len(cache),
        "wrong_n_dir": dict(dirs),
        "n_class": dict(ncls),
        "ratio_hist": dict(ratios.most_common(12)),
        "held_out": {"n": len(hold), "classified": hold_ok, "unknown": len(hold) - hold_ok},
        "train_class": dict(Counter(r["class"] for r in train)),
        "assoc_class": dict(acls),
        "n_examples": n_rows[:10],
        "assoc_examples": a_rows[:8],
        "clean_virtual": len(cleans),
        "frozen_rules": {
            N_CLAMPED: "n_exec = published_base - before_base; encoded is requested > executed",
            N_BALANCE_DERIVED: "n_exec = user base ATA debit / vault base credit",
            N_PREVIOUS_OUTPUT: "encoded is another transfer or another Pump CPI amount",
            N_INVERSE_QUOTE: "n_exec inverted from published quote vault",
            N_LITERAL: "some Pump-leg amount_in already equals n_exec; predictor picked the wrong one",
            N_UNKNOWN: "fail closed; do not invent amount_in",
        },
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PUMP015_N.json").write_text(json.dumps(doc, indent=2, default=str) + "\n")
    lines = [
        "# PUMP-N-015 reducer",
        "",
        f"wrong-N: {len(wrong)}  assoc: {len(assoc)}  cached_tx: {len(cache)}",
        f"dir: {dict(dirs)}",
        "",
        "## N class",
    ]
    for k, v in ncls.most_common():
        lines.append(f"- {k}: {v}")
    lines += ["", f"held-out classified {hold_ok}/{len(hold)}", "", "## association", ""]
    for k, v in acls.most_common():
        lines.append(f"- {k}: {v}")
    md = "\n".join(lines) + "\n"
    (outdir / "PUMP015_N.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
