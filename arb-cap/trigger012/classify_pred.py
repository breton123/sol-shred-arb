#!/usr/bin/env python3
"""Classify each predecessor: pre-exec fields vs executed inner N.

Does not invent S'. Groups router shapes into:
  EXACT_DIRECT
  EXACT_ROUTER          (amount recovered from outer ix)
  DETERMINISTIC_WITH_S  (needs cached local state — flagged, not quoted)
  UNPREDICTABLE_PREEXEC (inner amount not in pre-exec fields)
  RELEVANT_UNKNOWN      (touched supported DEX, not yet decided)
"""
from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "arb-cap" / "trigger011"))
from hist_funnel011 import load_univ  # noqa: E402
from rpc_url import rpc_url  # noqa: E402
from b58 import ALPH

PRED = HERE / "predecessors.jsonl"
TXC = HERE / "tx"
UNIV = ROOT / "arb-cap" / "regress" / "liveuniv_now.json"
ALTJ = ROOT / "arb-cap" / "trigger011" / "alt_cache.json"
OUT = HERE / "funnel012.jsonl"
CORPUS = HERE / "corpus.jsonl"
DASH = HERE / "dashboard.json"

DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
INFRA = {
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "AddressLookupTab1e1111111111111111111111111",
}
PUMP_SELL = bytes.fromhex("33e685a4017f83ad")
PUMP_BUY_EQ = bytes.fromhex("c62e1552b4d9e870")
PUMP_BUY = bytes.fromhex("66063d1201daebea")
DLMM_SWAP2 = bytes.fromhex("414b3f4ceb5b5b88")
DLMM_SWAP1 = bytes.fromhex("f8c69e91e17587c8")


def b58raw(s: str) -> bytes:
    n = 0
    for ch in s:
        i = ALPH.find(ch)
        if i < 0:
            return b""
        n = n * 58 + i
    raw = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    pad = 0
    for ch in s:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + raw.lstrip(b"\x00")


def cache_path(sig: str) -> Path:
    return TXC / sig[:2] / f"{sig}.json.gz"


def load_tx(sig: str) -> dict | None:
    p = cache_path(sig)
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_tx(sig: str, obj: dict) -> None:
    p = cache_path(sig)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(obj, f)


def rpc(url, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def fetch_one(url: str, sig: str) -> None:
    if load_tx(sig) is not None:
        return
    last = None
    for i in range(4):
        try:
            doc = rpc(url, "getTransaction", [sig, {
                "encoding": "json",
                "maxSupportedTransactionVersion": 1,
                "commitment": "confirmed",
            }])
            if doc.get("error"):
                last = doc["error"]
                time.sleep(0.3 * (i + 1))
                continue
            save_tx(sig, doc.get("result") or {})
            return
        except Exception as e:
            last = str(e)
            time.sleep(0.3 * (i + 1))
    save_tx(sig, {"_error": str(last)})


def pk_of(k) -> str | None:
    if isinstance(k, str):
        return k
    if isinstance(k, dict):
        return k.get("pubkey")
    return None


def resolved_keys(tx: dict) -> list[str]:
    msg = (tx.get("transaction") or {}).get("message") or {}
    meta = tx.get("meta") or {}
    keys = [pk_of(k) for k in (msg.get("accountKeys") or [])]
    loaded = meta.get("loadedAddresses") or {}
    wr = [pk_of(k) or k for k in (loaded.get("writable") or [])]
    ro = [pk_of(k) or k for k in (loaded.get("readonly") or [])]
    return [k for k in keys + wr + ro if k]


def inner_dex_ops(tx: dict) -> list[dict]:
    """Executed Pump/DLMM logical swaps from inner+outer ix data."""
    msg = (tx.get("transaction") or {}).get("message") or {}
    meta = tx.get("meta") or {}
    keys = resolved_keys(tx)
    ops = []

    def walk(ix, where: str):
        pid = ix.get("programId")
        if pid is None:
            idx = ix.get("programIdIndex")
            if isinstance(idx, int) and idx < len(keys):
                pid = keys[idx]
        if pid not in (DLMM, PUMP):
            return
        data_s = ix.get("data") or ""
        raw = b58raw(data_s) if data_s else b""
        accs = []
        for a in ix.get("accounts") or []:
            if isinstance(a, int) and a < len(keys):
                accs.append(keys[a])
            elif isinstance(a, str):
                accs.append(a)
            elif isinstance(a, dict) and a.get("pubkey"):
                accs.append(a["pubkey"])
        pool = accs[0] if accs else None
        amt = int.from_bytes(raw[8:16], "little") if len(raw) >= 16 else None
        disc = raw[:8].hex() if len(raw) >= 8 else ""
        direction = None
        if raw[:8] == PUMP_SELL:
            direction = "base_to_quote"
        elif raw[:8] in (PUMP_BUY_EQ, PUMP_BUY):
            direction = "quote_to_base"
        elif raw[:8] in (DLMM_SWAP2, DLMM_SWAP1):
            direction = "dlmm"
        ops.append({
            "where": where,
            "proto": "pump" if pid == PUMP else "dlmm",
            "pool": pool,
            "amount_in": amt,
            "disc": disc,
            "data_len": len(raw),
            "direction": direction,
            "buy_exact_out": raw[:8] == PUMP_BUY,
        })

    for ix in msg.get("instructions") or []:
        walk(ix, "outer")
    for g in meta.get("innerInstructions") or []:
        for ix in g.get("instructions") or []:
            walk(ix, "inner")
    return ops


def outer_venues(tx: dict) -> list[str]:
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = resolved_keys(tx)
    out = []
    seen = set()
    for ix in msg.get("instructions") or []:
        pid = ix.get("programId")
        if pid is None:
            idx = ix.get("programIdIndex")
            if isinstance(idx, int) and idx < len(keys):
                pid = keys[idx]
        if not pid or pid in INFRA or pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
    return out


def outer_payloads(tx: dict) -> list[dict]:
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = resolved_keys(tx)
    rows = []
    for ix in msg.get("instructions") or []:
        pid = ix.get("programId")
        if pid is None:
            idx = ix.get("programIdIndex")
            if isinstance(idx, int) and idx < len(keys):
                pid = keys[idx]
        if not pid or pid in INFRA:
            continue
        data_s = ix.get("data") or ""
        raw = b58raw(data_s) if data_s else b""
        rows.append({
            "program": pid,
            "disc": raw[:8].hex() if len(raw) >= 8 else "",
            "data_hex": raw.hex(),
            "data_len": len(raw),
        })
    return rows


def amount_in_outer(ops: list[dict], payloads: list[dict]) -> str:
    """Is each executed amount a function of outer bytes alone?"""
    amts = [op["amount_in"] for op in ops if op.get("amount_in")]
    if not amts:
        return "no_inner_amount"
    blob = b"".join(bytes.fromhex(p["data_hex"]) for p in payloads if p.get("data_hex"))
    if not blob:
        return "no_outer_data"
    hits = 0
    for a in amts:
        le = a.to_bytes(8, "little")
        if le in blob:
            hits += 1
    if hits == len(amts):
        return "amount_in_outer_bytes"
    if hits:
        return "partial_amount_in_outer"
    return "amount_absent_from_outer"


def classify_one(rec: dict, tx: dict | None, watch: dict, alts: dict) -> dict:
    usd = rec.get("usd") or 0
    out = {
        "winner": rec["winner"],
        "pred_sig": rec.get("pred_sig"),
        "slot": rec.get("slot"),
        "usd": usd,
        "pred_why": rec.get("pred_why"),
        "stage": "no_predecessor",
    }
    if not rec.get("pred_sig"):
        return out
    if not tx or tx.get("_error"):
        out["stage"] = "pred_tx_missing"
        return out
    meta = tx.get("meta") or {}
    if meta.get("err"):
        out["stage"] = "pred_failed"
        return out
    keys = resolved_keys(tx)
    ops = inner_dex_ops(tx)
    payloads = outer_payloads(tx)
    venues = outer_venues(tx)
    pools = [op["pool"] for op in ops if op.get("pool")]
    supported = [p for p in pools if p]
    in_univ = [p for p in supported if p in watch]
    out.update({
        "outer": venues,
        "n_loaded": len(keys),
        "ops": ops,
        "payloads": payloads,
        "pools": supported,
        "in_univ": in_univ,
        "shape": "direct" if any(op["where"] == "outer" for op in ops) and all(
            v in (DLMM, PUMP) for v in venues) else (
            "cpi" if any(op["where"] == "inner" for op in ops) and not any(
                op["where"] == "outer" for op in ops) else (
                "mixed" if ops else "no_dex_op")),
    })
    # framing from first signature + message is implicit: we have a full RPC tx
    out["framed"] = True
    out["alt_resolved"] = True  # RPC loadedAddresses is the resolved vector
    out["supported_touch"] = bool(supported)
    out["univ_hit"] = bool(in_univ)
    out["amount_locus"] = amount_in_outer(ops, payloads)

    raw = None
    # Cannot reconstruct wire bytes from json encoding easily. Use ops.
    direct_ops = [op for op in ops if op["where"] == "outer" and op.get("amount_in") and not op.get("buy_exact_out")]
    if direct_ops and out["shape"] == "direct":
        out["stage"] = "exact_direct"
        out["can_sprime"] = True
        return out
    if out["shape"] in ("cpi", "mixed"):
        if out["amount_locus"] == "amount_in_outer_bytes":
            out["stage"] = "exact_router_candidate"
            out["can_sprime"] = False  # candidate until bit-for-bit decoder exists
            return out
        if out["amount_locus"] == "amount_absent_from_outer":
            out["stage"] = "unpredictable_preexec"
            out["can_sprime"] = False
            return out
        out["stage"] = "relevant_unknown"
        out["can_sprime"] = False
        return out
    if supported and not in_univ:
        out["stage"] = "pool_not_in_universe"
        out["can_sprime"] = False
        return out
    if not supported:
        out["stage"] = "no_supported_dex"
        return out
    out["stage"] = "relevant_unknown"
    return out


def dash_table(rows: list[dict]) -> list[dict]:
    acc = defaultdict(lambda: {"n": 0, "usd": 0.0})
    for r in rows:
        acc[r["stage"]]["n"] += 1
        acc[r["stage"]]["usd"] += r.get("usd") or 0
    return [{"stage": k, **v} for k, v in sorted(acc.items(), key=lambda kv: -kv[1]["usd"])]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    preds = [json.loads(l) for l in PRED.read_text(encoding="utf-8").splitlines() if l.strip()]
    url = rpc_url()
    need = [r["pred_sig"] for r in preds if r.get("pred_sig") and load_tx(r["pred_sig"]) is None]
    need = list(dict.fromkeys(need))
    print(f"preds={len(preds)} fetch={len(need)}", flush=True)
    if need:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(fetch_one, url, s) for s in need]
            done = 0
            for fut in as_completed(futs):
                fut.result()
                done += 1
                if done % 50 == 0:
                    print(f"  fetched {done}/{len(need)}", flush=True)
    watch = load_univ(UNIV)
    alts = json.loads(ALTJ.read_text(encoding="utf-8")) if ALTJ.exists() else {}
    scored = []
    corpus = []
    for rec in preds:
        tx = load_tx(rec["pred_sig"]) if rec.get("pred_sig") else None
        row = classify_one(rec, tx, watch, alts)
        scored.append(row)
        if row.get("shape") in ("cpi", "mixed"):
            corpus.append({
                "pred_sig": row.get("pred_sig"),
                "usd": row.get("usd"),
                "outer": row.get("outer"),
                "payloads": row.get("payloads"),
                "ops": row.get("ops"),
                "amount_locus": row.get("amount_locus"),
                "stage": row.get("stage"),
                "pools": row.get("pools"),
                "in_univ": row.get("in_univ"),
            })
    OUT.write_text("".join(json.dumps(x) + "\n" for x in scored), encoding="utf-8")
    CORPUS.write_text("".join(json.dumps(x) + "\n" for x in corpus), encoding="utf-8")
    total_n = len(scored)
    total_usd = sum(r["usd"] for r in scored)
    stages = dash_table(scored)
    # explainable = exact_direct + unpredictable + pool_not_in_universe + feed/pred miss classified
    explain = {"exact_direct", "unpredictable_preexec", "pool_not_in_universe",
               "no_predecessor", "pred_tx_missing", "no_supported_dex", "pred_failed"}
    exp_usd = sum(r["usd"] for r in scored if r["stage"] in explain)
    unk_usd = sum(r["usd"] for r in scored if r["stage"] in ("relevant_unknown", "exact_router_candidate"))
    pools = Counter()
    for r in scored:
        for p in r.get("pools") or []:
            pools[p] += 1
    dash = {
        "n": total_n,
        "usd": total_usd,
        "stages": stages,
        "explained_usd": exp_usd,
        "explained_pct": (100.0 * exp_usd / total_usd) if total_usd else 0,
        "unknown_usd": unk_usd,
        "unique_pools_touched": len(pools),
        "pools_in_univ": sum(1 for p in pools if p in watch),
        "pools_missing": sum(1 for p in pools if p not in watch),
        "corpus": len(corpus),
        "shape": dict(Counter(r.get("shape") or "none" for r in scored)),
        "amount_locus": dict(Counter(r.get("amount_locus") or "n/a" for r in scored if r.get("amount_locus"))),
    }
    DASH.write_text(json.dumps(dash, indent=2), encoding="utf-8")
    print(f"LIVE HOUR  n={total_n}  ${total_usd:.1f}")
    print(f"{'stage':<32} {'N':>6} {'$':>10}")
    for s in stages:
        print(f"{s['stage']:<32} {s['n']:6} {s['usd']:10.1f}")
    print(f"explained ${exp_usd:.1f} ({dash['explained_pct']:.1f}%)  unknown ${unk_usd:.1f}")
    print(f"unique supported pools touched={len(pools)} in_univ={dash['pools_in_univ']} missing={dash['pools_missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
