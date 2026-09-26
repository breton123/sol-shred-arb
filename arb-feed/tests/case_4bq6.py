#!/usr/bin/env python3
"""4BQ6AT teardown — same questions as MRIYA_CASE_STUDY, public chain + trial dump."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
sys.path.insert(0, str(ARB))
from dataset.env import helius_api_key, helius_rpc_url  # noqa: E402

WALLET = "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK"
MRIYA = "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X"
AN225 = "AN225ykGPAmckE9uMCCM7jQv3L3AYwiPZbHqgMUYEgCR"
NONCE_PROG = "11111111111111111111111111111111"
ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
OUT = ROOT / "arb-cap" / "case_4bq6"
ALL = ROOT / "arb-cap" / "all_arbs_trial.jsonl"
PAIRS = ROOT / "arb-cap" / "cap004_s25" / "pairs.jsonl"
KNOWN_CEX = {
    "2AQdpHJ2JpcEgPiATUXjQxA8QmafFegfQwSLWSweJWzY": "Coinbase",
    "H8sMJSCQxfKiFTCfDR3DUMLPwcRZMYyF4hKKnyR6HLtH": "Coinbase",
    "2ojv9BAiHUrvsm9gxDe7fJSzbNZSJcxZvf8dqmWGHG8S": "Coinbase",
    "D89hHJT5Aqyx1trP6fPAqM5sqcyNwy0364yA3bgY5gxo": "Coinbase",
    "FpwQQhQQoEaVu3WU2qZMfF1hx48YyfwsLoLKrSSnyZt": "Coinbase",
    "A77HErqtfN1hLLpgdeSESsU7Cg7kxK8wFHDFQdSuuBNP": "Coinbase",
    "GJRs4FwHtemZ5ZE9x3FNvJ8TMwitKTh21yxdRPqn7npE": "Coinbase",
    "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9": "Binance",
    "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "Binance",
    "AC5RDfQFmDS1deWZosHWGiUg5FN4LXreKM8Gbq7cVC4Z": "Binance",
    "5VCwKtCXgCJ6kit5FybXjvriW3xELsFDhYrPSqtJNmcD": "OKX",
    "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ": "Kraken",
}


def rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(helius_rpc_url(), data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def parsed_tx(sig):
    body = rpc(
        "getTransaction",
        [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}],
    )
    return body.get("result")


def all_signatures(limit_pages=80):
    out = []
    before = None
    for i in range(limit_pages):
        opts = {"limit": 1000}
        if before:
            opts["before"] = before
        body = rpc("getSignaturesForAddress", [WALLET, opts])
        batch = body.get("result") or []
        if not batch:
            break
        out.extend(batch)
        before = batch[-1]["signature"]
        print(f"  sigs {len(out)} page {i+1}", flush=True)
        if len(batch) < 1000:
            break
        time.sleep(0.05)
    return out


def helius_history(before=None, limit=100):
    key = helius_api_key()
    q = {"api-key": key, "limit": str(limit)}
    if before:
        q["before"] = before
    url = f"https://api.helius.xyz/v0/addresses/{WALLET}/transactions?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def keys_of(tx):
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = []
    for k in msg.get("accountKeys") or []:
        keys.append(k.get("pubkey") if isinstance(k, dict) else k)
    loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
    keys += list(loaded.get("writable") or []) + list(loaded.get("readonly") or [])
    return keys, msg


def native_delta(tx, wallet):
    keys, _ = keys_of(tx)
    if wallet not in keys:
        return 0
    idx = keys.index(wallet)
    pre = (tx.get("meta") or {}).get("preBalances") or []
    post = (tx.get("meta") or {}).get("postBalances") or []
    if idx >= len(pre) or idx >= len(post):
        return 0
    return post[idx] - pre[idx]


def ix_programs(tx):
    _, msg = keys_of(tx)
    pids = []
    for ix in msg.get("instructions") or []:
        pid = ix.get("programId")
        if pid:
            pids.append(pid)
        parsed = ix.get("parsed") if isinstance(ix, dict) else None
        if isinstance(parsed, dict) and parsed.get("type"):
            pids.append("parsed:" + parsed.get("type"))
    inner = (tx.get("meta") or {}).get("innerInstructions") or []
    for group in inner:
        for ix in group.get("instructions") or []:
            pid = ix.get("programId")
            if pid:
                pids.append("inner:" + pid)
    return pids


def trial_stats():
    rows = []
    for line in ALL.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("user") == WALLET:
            rows.append(r)
    hops = Counter(r.get("number_of_swap_steps") for r in rows)
    routes = Counter(" → ".join(r.get("dexes") or []) for r in rows)
    providers = Counter(r.get("provider") or r.get("landing") or "unset")
    fees = [float(r.get("fee_usd") or r.get("priority_fee_usd") or 0) for r in rows]
    return {
        "n": len(rows),
        "profit": sum(float(r.get("pure_profit") or 0) for r in rows),
        "hops": dict(hops),
        "routes": routes.most_common(12),
        "providers": dict(providers),
        "fee_p50": sorted(fees)[len(fees) // 2] if fees else None,
        "sample_keys": sorted({k for r in rows[:5] for k in r.keys()}),
    }


def cached_pair_fingerprint():
    progs = Counter()
    nonce = 0
    an225 = 0
    n = 0
    if not PAIRS.exists():
        return {}
    for line in PAIRS.read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        if p.get("user") != WALLET:
            continue
        hx = p.get("mriya_tx_hex") or ""
        if not hx:
            continue
        n += 1
        raw = bytes.fromhex(hx)
        # cheap: look for known 32-byte program ids in account keys region
        if AN225.encode() or True:
            # scan hex string for known base58 later via rpc sample
            pass
        if "AdvanceNonce" in hx:
            nonce += 1
    return {"cached_txs": n, "note": "hex scan only; programs from RPC samples"}


def das_assets():
    url = helius_rpc_url()
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "getAssetsByOwner",
        "params": {
            "ownerAddress": WALLET,
            "page": 1,
            "limit": 1000,
            "displayOptions": {"showFungible": True, "showNativeBalance": True},
        },
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("trial dump...", flush=True)
    trial = trial_stats()
    print("trial", trial["n"], trial["profit"], trial["hops"], flush=True)
    (OUT / "trial_stats.json").write_text(json.dumps(trial, indent=2, default=str), encoding="utf-8")

    print("signatures...", flush=True)
    sigs = all_signatures()
    (OUT / "signatures.json").write_text(json.dumps(sigs), encoding="utf-8")
    times = [s.get("blockTime") for s in sigs if s.get("blockTime")]
    err_n = sum(1 for s in sigs if s.get("err"))
    print(f"  {len(sigs)} sigs err={err_n} first={min(times) if times else None}", flush=True)

    bal = rpc("getBalance", [WALLET])
    sol = ((bal.get("result") or {}).get("value") or 0) / 1e9
    print("SOL", sol, flush=True)

    print("DAS...", flush=True)
    try:
        assets = das_assets()
        (OUT / "das_assets.json").write_text(json.dumps(assets), encoding="utf-8")
    except Exception as e:
        assets = {"error": str(e)}
        print("DAS fail", e, flush=True)

    oldest = sigs[-1]["signature"] if sigs else None
    newest = sigs[0]["signature"] if sigs else None
    print("sample txs...", flush=True)
    sample_idx = []
    if sigs:
        sample_idx.append(("newest", 0))
        sample_idx.append(("oldest", len(sigs) - 1))
        # first 25 chronological (end of list)
        for i in range(max(0, len(sigs) - 25), len(sigs)):
            sample_idx.append(("birth", i))
        step = max(1, len(sigs) // 20)
        for i in range(0, len(sigs), step):
            sample_idx.append(("stride", i))
        # 25 recent successes / fails
        fails = [i for i, s in enumerate(sigs) if s.get("err")][:15]
        oks = [i for i, s in enumerate(sigs) if not s.get("err")][:15]
        for i in fails:
            sample_idx.append(("fail", i))
        for i in oks:
            sample_idx.append(("ok", i))

    seen = set()
    programs = Counter()
    parsed_types = Counter()
    nonce_ix = 0
    an225_ix = 0
    bpf = 0
    samples = []
    funding = []
    cex = []
    for tag, i in sample_idx:
        sig = sigs[i]["signature"]
        if sig in seen:
            continue
        seen.add(sig)
        tx = parsed_tx(sig)
        time.sleep(0.05)
        if not tx:
            continue
        keys, msg = keys_of(tx)
        pids = ix_programs(tx)
        for pid in pids:
            if pid.startswith("parsed:"):
                parsed_types[pid] += 1
            elif pid.startswith("inner:"):
                programs[pid] += 1
            else:
                programs[pid] += 1
        if any(p == AN225 or p.endswith(AN225) for p in pids):
            an225_ix += 1
        if any("advanceNonce" in p or p == "parsed:advanceNonceAccount" for p in pids):
            nonce_ix += 1
        if any("BPFLoader" in (k or "") or k == "BPFLoaderUpgradeab1e11111111111111111111111" for k in keys):
            bpf += 1
        for k in keys:
            if k in KNOWN_CEX:
                cex.append({"sig": sig, "label": KNOWN_CEX[k], "acct": k, "time": tx.get("blockTime")})
        d = native_delta(tx, WALLET)
        if d > 5e8:
            funding.append(
                {
                    "sig": sig,
                    "tag": tag,
                    "time": tx.get("blockTime"),
                    "iso": datetime.fromtimestamp(tx["blockTime"], tz=timezone.utc).isoformat() if tx.get("blockTime") else None,
                    "sol_in": d / 1e9,
                    "fee_payer": keys[0] if keys else None,
                    "accounts": keys[:16],
                    "pids": pids[:12],
                }
            )
        samples.append(
            {
                "tag": tag,
                "sig": sig,
                "err": (tx.get("meta") or {}).get("err"),
                "fee": (tx.get("meta") or {}).get("fee"),
                "slot": tx.get("slot"),
                "time": tx.get("blockTime"),
                "pids": pids,
                "nkeys": len(keys),
            }
        )

    print("helius enhanced (funding)...", flush=True)
    enhanced = []
    before = None
    try:
        for page in range(40):
            batch = helius_history(before=before, limit=100)
            if not batch:
                break
            enhanced.extend(batch)
            before = batch[-1].get("signature")
            t = batch[-1].get("timestamp")
            print(f"  enh {page+1} n={len(enhanced)} oldest={t}", flush=True)
            if t and times and t < (min(times) - 86400):
                break
            if len(batch) < 100:
                break
            time.sleep(0.12)
    except Exception as e:
        print("enhanced fail", e, flush=True)
    (OUT / "helius_enhanced.json").write_text(json.dumps(enhanced), encoding="utf-8")

    inflows = []
    for tx in enhanced:
        ts = tx.get("timestamp")
        for ntr in tx.get("nativeTransfers") or []:
            if ntr.get("toUserAccount") == WALLET and (ntr.get("amount") or 0) >= 1e8:
                inflows.append(
                    {
                        "sig": tx.get("signature"),
                        "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
                        "sol": (ntr.get("amount") or 0) / 1e9,
                        "from": ntr.get("fromUserAccount"),
                        "type": tx.get("type"),
                        "source": tx.get("source"),
                        "desc": tx.get("description"),
                    }
                )

    first_iso = datetime.fromtimestamp(min(times), tz=timezone.utc).isoformat() if times else None
    last_iso = datetime.fromtimestamp(max(times), tz=timezone.utc).isoformat() if times else None
    summary = {
        "wallet": WALLET,
        "n_signatures": len(sigs),
        "err_n": err_n,
        "err_rate": err_n / len(sigs) if sigs else None,
        "first_sig": oldest,
        "last_sig": newest,
        "first_iso": first_iso,
        "last_iso": last_iso,
        "sol_balance": sol,
        "trial": trial,
        "programs_sampled": programs.most_common(30),
        "parsed_types": parsed_types.most_common(20),
        "nonce_ix_in_sample": nonce_ix,
        "an225_ix_in_sample": an225_ix,
        "bpf_in_sample": bpf,
        "sample_n": len(samples),
        "funding_rpc": funding,
        "cex_hits": cex,
        "enhanced_inflows": inflows[:40],
        "das_error": assets.get("error") if isinstance(assets, dict) else None,
    }
    (OUT / "samples.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    (OUT / "summary_raw.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k not in ("funding_rpc", "enhanced_inflows", "trial")}, indent=2, default=str))


if __name__ == "__main__":
    main()
