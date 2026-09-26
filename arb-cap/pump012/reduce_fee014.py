#!/usr/bin/env python3
"""PUMP-FEE-014 — quote-token conservation on the unexplained buy residuals.

Does not deploy. Does not fit a global bps. Clusters residual, then traces
every quote-mint transfer in the executed transaction.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from reduce_buy013 import collect, fee, pred_buy_quote
from replay import _dir_amt

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
TOK2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
WSOL = "So11111111111111111111111111111111111111112"


def b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    pad = 0
    for b in raw:
        if b == 0:
            pad += 1
        else:
            break
    return B58[0] * pad + (out or B58[0])


def rpc(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    last = None
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode())
            if data.get("error"):
                last = data["error"]
                time.sleep(0.15 * (i + 1))
                continue
            return data.get("result")
        except Exception as e:
            last = e
            time.sleep(0.15 * (i + 1))
    return None


def expect_dq(ain: int, lp_b: int, pr_b: int, cr_b: int) -> int:
    tot = lp_b + pr_b + cr_b
    if tot >= 10000:
        return -1
    eff = ain * 10000 // (10000 + tot)
    return ain - fee(eff, pr_b) - fee(eff, cr_b)


def fetch_pool_meta(url: str, pks: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(pks), 80):
        chunk = pks[i:i + 80]
        vals = rpc(url, "getMultipleAccounts", [chunk, {"encoding": "base64"}])
        if not vals:
            continue
        import base64
        for pk, acc in zip(chunk, vals.get("value") or []):
            if not acc:
                continue
            raw = base64.b64decode(acc["data"][0])
            out[pk] = {
                "creator_bps": int.from_bytes(raw[261:269], "little") if len(raw) >= 269 else None,
                "holder": raw[270] if len(raw) > 270 else None,
                "cashback": raw[244] if len(raw) > 244 else None,
                "mayhem": raw[243] if len(raw) > 243 else None,
                "virt": int.from_bytes(raw[245:261], "little", signed=True) if len(raw) >= 261 else None,
                "len": len(raw),
            }
    return out


def classify_row(b: dict, live: dict | None) -> str:
    sb, pu = b["s_before"], b["published_s"]
    _, ain = _dir_amt(b)
    pred, fees = pred_buy_quote(sb, ain)
    pub = int(pu["reserve_quote"]) - int(sb["reserve_quote"])
    cr = (live or {}).get("creator_bps")
    lp_b, pr_b = int(sb["lp_fee_bps"]), int(sb["protocol_fee_bps"])
    if cr is not None and expect_dq(ain, lp_b, pr_b, cr) == pub:
        return "pool_creator"
    if ain - fees["proto"] == pub:
        return "proto_only"
    if expect_dq(ain, lp_b, pr_b, 0) == pub:
        return "creator0"
    return "unexplained"


def quote_deltas(tx: dict, quote_mint: str) -> dict[str, int]:
    meta = (tx.get("meta") or {})
    keys = []
    msg = (tx.get("transaction") or {}).get("message") or {}
    accs = msg.get("accountKeys") or []
    for a in accs:
        if isinstance(a, dict):
            keys.append(a.get("pubkey") or "")
        else:
            keys.append(str(a))
    # loaded addresses
    la = meta.get("loadedAddresses") or {}
    keys.extend(la.get("writable") or [])
    keys.extend(la.get("readonly") or [])
    pre = {(b.get("accountIndex"), b.get("mint")): int((b.get("uiTokenAmount") or {}).get("amount") or 0)
           for b in (meta.get("preTokenBalances") or [])}
    post = {(b.get("accountIndex"), b.get("mint")): int((b.get("uiTokenAmount") or {}).get("amount") or 0)
            for b in (meta.get("postTokenBalances") or [])}
    idxs = set(i for i, m in list(pre) + list(post) if m == quote_mint)
    out = {}
    for i in idxs:
        if i is None or i >= len(keys):
            continue
        d = post.get((i, quote_mint), 0) - pre.get((i, quote_mint), 0)
        if d:
            out[keys[i]] = d
    return out


def role_of(pk: str, ix_accs: list[str]) -> str:
    # buy_exact_quote_in layout from IDL
    names = [
        "pool", "user", "global_config", "base_mint", "quote_mint",
        "user_base", "user_quote", "pool_base", "pool_quote",
        "protocol_fee_recipient", "protocol_fee_ata",
        "base_token_program", "quote_token_program", "system", "ata_program",
        "event_authority", "program", "coin_creator_vault_ata",
        "coin_creator_vault_authority", "global_volume_accumulator",
        "user_volume_accumulator",
    ]
    try:
        i = ix_accs.index(pk)
    except ValueError:
        return "other"
    if i < len(names):
        return names[i]
    return f"remaining_{i}"


def pump_ix_accounts(tx: dict) -> list[str]:
    msg = (tx.get("transaction") or {}).get("message") or {}
    accs = []
    for a in msg.get("accountKeys") or []:
        accs.append(a.get("pubkey") if isinstance(a, dict) else str(a))
    la = ((tx.get("meta") or {}).get("loadedAddresses") or {})
    loaded = list(la.get("writable") or []) + list(la.get("readonly") or [])
    # find pump buy_exact in compiled or parsed ixs
    ixs = msg.get("instructions") or []
    for ix in ixs:
        prog = ix.get("programId") or ""
        if isinstance(ix.get("programIdIndex"), int):
            pi = ix["programIdIndex"]
            if pi < len(accs):
                prog = accs[pi]
        if prog != "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA":
            continue
        out = []
        if "accounts" in ix and ix["accounts"] and isinstance(ix["accounts"][0], str):
            return list(ix["accounts"])
        for ai in ix.get("accounts") or []:
            if isinstance(ai, int) and ai < len(accs) + len(loaded):
                keys = accs + loaded
                out.append(keys[ai])
        if out:
            return out
    return []


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
    buys, _ = collect(root / "mismatch", meta)
    pks = sorted({meta[int(b["idx"])]["pubkey"] for b in buys if int(b["idx"]) in meta})
    live = fetch_pool_meta(url, pks)
    live_by_idx = {i: live.get(meta[i]["pubkey"], {}) for i in meta}

    buckets = Counter()
    unexplained = []
    for b in buys:
        idx = int(b["idx"])
        tag = classify_row(b, live_by_idx.get(idx))
        buckets[tag] += 1
        if tag == "unexplained":
            unexplained.append(b)

    rows = []
    by_idx = defaultdict(list)
    mint_n = Counter()
    bps_n = Counter()
    for b in unexplained:
        sb, pu = b["s_before"], b["published_s"]
        _, ain = _dir_amt(b)
        pred, fees = pred_buy_quote(sb, ain)
        pub = int(pu["reserve_quote"]) - int(sb["reserve_quote"])
        res = pub - pred  # actual - expected (user asked this sign)
        # also keep pred-pub as leave_short
        idx = int(b["idx"])
        p = meta.get(idx) or {}
        qmint = p.get("my") or p.get("mx") or "?"
        r = {
            "sig": b.get("trigger_sig") or b.get("sig"),
            "idx": idx,
            "pool": b.get("pool") or p.get("pubkey"),
            "spendable": ain,
            "vault_delta": pub,
            "expected_vault_delta": pred,
            "residual": res,
            "leave_short": pred - pub,
            "protocol_fee": fees["proto"],
            "creator_fee": fees["creator"],
            "lp_fee": fees["lp"],
            "residual_bps": round((pred - pub) * 10000 / ain) if ain else None,
            "quote_mint": qmint,
            "base_mint": p.get("mx"),
            "live": live_by_idx.get(idx),
        }
        rows.append(r)
        by_idx[idx].append(r)
        mint_n[qmint] += 1
        bps_n[r["residual_bps"]] += 1

    # per-pool residual tightness
    pool_summ = []
    for idx, rs in sorted(by_idx.items(), key=lambda kv: -len(kv[1])):
        shorts = [x["leave_short"] for x in rs]
        bpss = [x["residual_bps"] for x in rs]
        ains = [x["spendable"] for x in rs]
        # stable ceil(spendable*bps/10000)==leave_short?
        stable = None
        for bps in range(0, 400):
            if all(fee(a, bps) == s for a, s in zip(ains, shorts)):
                stable = bps
                break
        pool_summ.append({
            "idx": idx, "n": len(rs), "pool": rs[0]["pool"],
            "quote_mint": rs[0]["quote_mint"],
            "live": rs[0]["live"],
            "bps_mode": Counter(bpss).most_common(1)[0],
            "bps_unique": sorted(set(bpss)),
            "stable_ceil_bps": stable,
            "creator": (rs[0]["live"] or {}).get("creator_bps"),
            "holder": (rs[0]["live"] or {}).get("holder"),
            "cashback": (rs[0]["live"] or {}).get("cashback"),
            "mayhem": (rs[0]["live"] or {}).get("mayhem"),
            "virt": (rs[0]["live"] or {}).get("virt"),
        })

    # fetch txs: all of idx 399 + up to 3 per other unexplained pool + all if <= 250
    txdir = outdir / "fee014_tx"
    txdir.mkdir(parents=True, exist_ok=True)
    want = []
    seen = set()
    for r in rows:
        if r["idx"] == 399 or r["sig"] not in seen:
            if r["idx"] == 399 or sum(1 for x in want if x["idx"] == r["idx"]) < 3:
                if r["sig"] and r["sig"] not in seen:
                    want.append(r)
                    seen.add(r["sig"])
    # if small, take all
    if len(unexplained) <= 220:
        want = [r for r in rows if r["sig"]]
        seen = {r["sig"] for r in want}

    transfers = []
    mystery = Counter()
    role_credit = Counter()
    conserve = Counter()
    tokprog = Counter()
    for i, r in enumerate(want):
        hx = r["sig"]
        if not hx:
            continue
        dest = txdir / f"{hx}.json"
        if dest.exists():
            tx = json.loads(dest.read_text())
        else:
            try:
                sig = b58encode(bytes.fromhex(hx))
            except Exception:
                continue
            tx = rpc(url, "getTransaction", [sig, {
                "encoding": "jsonParsed",
                "maxSupportedTransactionVersion": 2,
                "commitment": "confirmed",
            }])
            if tx:
                dest.write_text(json.dumps(tx))
            if i and i % 40 == 0:
                print(f"tx {i}/{len(want)}", flush=True)
        if not tx:
            conserve["tx_missing"] += 1
            continue
        qmint = r["quote_mint"]
        deltas = quote_deltas(tx, qmint)
        ix_accs = pump_ix_accounts(tx)
        labeled = []
        user_debit = 0
        pool_credit = 0
        proto_c = 0
        creator_c = 0
        other = []
        for pk, d in sorted(deltas.items(), key=lambda kv: -abs(kv[1])):
            role = role_of(pk, ix_accs) if ix_accs else "unknown"
            labeled.append({"pk": pk, "d": d, "role": role})
            if role == "user_quote" and d < 0:
                user_debit += -d
            elif role == "pool_quote" and d > 0:
                pool_credit += d
            elif role == "protocol_fee_ata" and d > 0:
                proto_c += d
            elif role == "coin_creator_vault_ata" and d > 0:
                creator_c += d
            elif d > 0:
                other.append({"pk": pk, "d": d, "role": role})
                mystery[f"{role}|{pk[:8]}"] += 1
            role_credit[role] += d
        # token program of quote mint from preTokenBalances
        prog = None
        for bal in ((tx.get("meta") or {}).get("preTokenBalances") or []):
            if bal.get("mint") == qmint:
                prog = bal.get("programId") or bal.get("program")
                break
        tokprog[prog or "?"] += 1
        spent = user_debit
        accounted = pool_credit + proto_c + creator_c + sum(x["d"] for x in other)
        gap = spent - accounted
        if spent and gap == 0:
            conserve["closed"] += 1
        elif spent:
            conserve["open"] += 1
        else:
            conserve["no_user_quote"] += 1
        transfers.append({
            "idx": r["idx"], "sig": hx, "spendable": r["spendable"],
            "vault_delta": r["vault_delta"], "residual_leave": r["leave_short"],
            "user_debit": user_debit, "pool_credit": pool_credit,
            "proto_credit": proto_c, "creator_credit": creator_c,
            "other": other, "gap": gap,
            "pool_vs_vault": pool_credit - r["vault_delta"],
            "mystery_vs_residual": (sum(x["d"] for x in other) - r["leave_short"]) if other else None,
            "token_program": prog,
        })

    # mystery vs residual on fetched
    match_mystery = sum(1 for t in transfers if t["other"] and t["mystery_vs_residual"] == 0)
    match_abs = sum(1 for t in transfers if t["other"] and abs(t["mystery_vs_residual"] or 1) <= 2)

    doc = {
        "n_buy_residual": len(buys),
        "class": dict(buckets),
        "n_unexplained": len(unexplained),
        "residual_bps_hist": dict(bps_n.most_common(15)),
        "quote_mint": dict(mint_n.most_common()),
        "pools": pool_summ,
        "tx_fetched": len(transfers),
        "conservation": dict(conserve),
        "token_program": dict(tokprog),
        "mystery_roles": dict(mystery.most_common(15)),
        "mystery_eq_residual": match_mystery,
        "mystery_near_residual": match_abs,
        "transfer_examples": [t for t in transfers if t["idx"] == 399][:4] + [
            t for t in transfers if t["other"] and t["idx"] != 399][:4],
    }
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "PUMP014_FEE.json").write_text(json.dumps(doc, indent=2) + "\n")
    lines = [
        "# PUMP-FEE-014",
        "",
        f"buy residuals {len(buys)}  unexplained {len(unexplained)}  class {dict(buckets)}",
        f"tx fetched {len(transfers)}  conservation {dict(conserve)}",
        f"mystery credits == residual: {match_mystery}  near: {match_abs}",
        f"token program {dict(tokprog)}",
        "",
        "## residual bps (leave_short / spendable)",
    ]
    for k, v in bps_n.most_common(10):
        lines.append(f"- {k} bps: {v}")
    lines += ["", "## unexplained pools (predicate hunt)", ""]
    for p in pool_summ[:16]:
        lines.append(
            f"- idx {p['idx']} n={p['n']} ceil_bps={p['stable_ceil_bps']} "
            f"mode={p['bps_mode']} cr={p['creator']} h={p['holder']} "
            f"cash={p['cashback']} virt={p['virt']} mint={(p['quote_mint'] or '')[:8]}"
        )
    lines += ["", "## mystery recipient roles", ""]
    for k, v in mystery.most_common(10):
        lines.append(f"- {k}: {v}")
    md = "\n".join(lines) + "\n"
    (outdir / "PUMP014_FEE.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
