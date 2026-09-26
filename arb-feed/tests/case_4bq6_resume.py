#!/usr/bin/env python3
"""Resume 4BQ6AT teardown: continue sigs, trial fields, slow parsed txs, enhanced funding."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
sys.path.insert(0, str(ARB))
from dataset.env import helius_api_key, helius_rpc_url  # noqa: E402

WALLET = "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK"
AN225 = "AN225ykGPAmckE9uMCCM7jQv3L3AYwiPZbHqgMUYEgCR"
ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
OUT = ROOT / "arb-cap" / "case_4bq6"
ALL = ROOT / "arb-cap" / "all_arbs_trial.jsonl"
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


def rpc(method, params, tries=6):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                helius_rpc_url(), data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            time.sleep(0.8 * (2**i))
        except Exception as e:
            last = e
            time.sleep(0.4 * (2**i))
    raise last


def parsed_tx(sig):
    body = rpc(
        "getTransaction",
        [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1, "commitment": "confirmed"}],
    )
    return body.get("result")


def continue_sigs(existing, extra_pages=120):
    before = existing[-1]["signature"] if existing else None
    out = list(existing)
    for i in range(extra_pages):
        opts = {"limit": 1000}
        if before:
            opts["before"] = before
        body = rpc("getSignaturesForAddress", [WALLET, opts])
        batch = body.get("result") or []
        if not batch:
            print("sigs done", len(out), flush=True)
            break
        out.extend(batch)
        before = batch[-1]["signature"]
        print(f"  sigs {len(out)} +page {i+1} oldest={batch[-1].get('blockTime')}", flush=True)
        if len(batch) < 1000:
            break
        time.sleep(0.08)
    return out


def keys_of(tx):
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = []
    for k in msg.get("accountKeys") or []:
        keys.append(k.get("pubkey") if isinstance(k, dict) else k)
    loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
    keys += list(loaded.get("writable") or []) + list(loaded.get("readonly") or [])
    return keys, msg


def ix_info(tx):
    keys, msg = keys_of(tx)
    top, parsed, inner = [], [], []
    nonce = False
    for ix in msg.get("instructions") or []:
        pid = ix.get("programId")
        if pid:
            top.append(pid)
        p = ix.get("parsed")
        if isinstance(p, dict):
            parsed.append(p.get("type"))
            if p.get("type") in ("advanceNonceAccount", "initializeNonceAccount", "authorizeNonceAccount"):
                nonce = True
    for group in (tx.get("meta") or {}).get("innerInstructions") or []:
        for ix in group.get("instructions") or []:
            pid = ix.get("programId")
            if pid:
                inner.append(pid)
    return {
        "keys": keys,
        "top": top,
        "parsed": parsed,
        "inner": inner,
        "nonce": nonce,
        "an225": AN225 in top or AN225 in inner or AN225 in keys,
        "err": (tx.get("meta") or {}).get("err"),
        "fee": (tx.get("meta") or {}).get("fee"),
        "cu": ((tx.get("meta") or {}).get("computeUnitsConsumed")),
        "slot": tx.get("slot"),
        "time": tx.get("blockTime"),
    }


def trial_rows():
    rows = []
    for line in ALL.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("user") == WALLET:
            rows.append(r)
    return rows


def helius_history(before=None, limit=100):
    key = helius_api_key()
    q = {"api-key": key, "limit": str(limit)}
    if before:
        q["before"] = before
    url = f"https://api.helius.xyz/v0/addresses/{WALLET}/transactions?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    last = None
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            time.sleep(0.8 * (2**i))
    raise last


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = trial_rows()
    providers = Counter(r.get("provider") for r in rows)
    aggs = Counter(r.get("aggregator") for r in rows)
    leaders = Counter(r.get("validator_name") for r in rows)
    cities = Counter(r.get("validator_city") for r in rows)
    tips = Counter(r.get("tip_type") for r in rows)
    fees = [float(r.get("priority_fee_usd") or 0) for r in rows]
    tip_usd = [float(r.get("tip") or 0) for r in rows]
    ticks = [r.get("tick_index") for r in rows if r.get("tick_index") is not None]
    trial = {
        "n": len(rows),
        "profit": sum(float(r.get("pure_profit") or 0) for r in rows),
        "profit_usd": sum(float(r.get("profit_usd") or 0) for r in rows),
        "providers": providers.most_common(),
        "aggregators": aggs.most_common(),
        "leaders": leaders.most_common(12),
        "cities": cities.most_common(8),
        "tip_type": tips.most_common(),
        "prio_fee_p50": sorted(fees)[len(fees) // 2] if fees else None,
        "prio_fee_max": max(fees) if fees else None,
        "tip_p50": sorted(tip_usd)[len(tip_usd) // 2] if tip_usd else None,
        "tick_p50": sorted(ticks)[len(ticks) // 2] if ticks else None,
        "hops": Counter(r.get("number_of_swap_steps") for r in rows).most_common(),
        "routes": Counter(" -> ".join(r.get("dexes") or []) for r in rows).most_common(),
    }
    (OUT / "trial_fields.json").write_text(json.dumps(trial, indent=2), encoding="utf-8")
    print("trial providers", trial["providers"], "aggs", trial["aggregators"][:6], flush=True)

    sig_path = OUT / "signatures.json"
    existing = json.loads(sig_path.read_text(encoding="utf-8")) if sig_path.exists() else []
    print("have sigs", len(existing), flush=True)
    sigs = continue_sigs(existing)
    sig_path.write_text(json.dumps(sigs), encoding="utf-8")
    times = [s.get("blockTime") for s in sigs if s.get("blockTime")]
    err_n = sum(1 for s in sigs if s.get("err"))
    print(f"sigs {len(sigs)} err={err_n} first={min(times) if times else None} last={max(times) if times else None}", flush=True)

    # pick txs: oldest 15, newest 15, 15 fails, 15 trial arbs, 10 stride
    want = []
    if sigs:
        want += [("newest", s["signature"]) for s in sigs[:15]]
        want += [("oldest", s["signature"]) for s in sigs[-15:]]
        want += [("fail", s["signature"]) for s in sigs if s.get("err")][:15]
        step = max(1, len(sigs) // 12)
        want += [("stride", sigs[i]["signature"]) for i in range(0, len(sigs), step)]
    want += [("trial", r["signature"]) for r in rows[:20]]
    seen = set()
    samples = []
    programs = Counter()
    nonce_n = an225_n = 0
    cex = []
    funding = []
    for tag, sig in want:
        if sig in seen:
            continue
        seen.add(sig)
        tx = parsed_tx(sig)
        time.sleep(0.2)
        if not tx:
            print("miss", sig[:12], flush=True)
            continue
        info = ix_info(tx)
        for p in info["top"]:
            programs[p] += 1
        for p in info["inner"]:
            programs["inner:" + p] += 1
        if info["nonce"]:
            nonce_n += 1
        if info["an225"]:
            an225_n += 1
        keys = info["keys"]
        for k in keys:
            if k in KNOWN_CEX:
                cex.append({"sig": sig, "label": KNOWN_CEX[k], "acct": k, "time": info["time"]})
        pre = (tx.get("meta") or {}).get("preBalances") or []
        post = (tx.get("meta") or {}).get("postBalances") or []
        if WALLET in keys:
            idx = keys.index(WALLET)
            if idx < len(pre) and idx < len(post) and post[idx] - pre[idx] > 5e8:
                funding.append(
                    {
                        "sig": sig,
                        "tag": tag,
                        "sol_in": (post[idx] - pre[idx]) / 1e9,
                        "time": info["time"],
                        "iso": datetime.fromtimestamp(info["time"], tz=timezone.utc).isoformat() if info["time"] else None,
                        "fee_payer": keys[0],
                        "top": info["top"],
                    }
                )
        samples.append({"tag": tag, "sig": sig, **{k: info[k] for k in info if k != "keys"}, "nkeys": len(keys)})
        print(f"  tx {len(samples)} {tag} top={info['top'][:4]} nonce={info['nonce']} err={bool(info['err'])}", flush=True)

    print("enhanced history...", flush=True)
    enhanced = []
    before = None
    try:
        for page in range(50):
            batch = helius_history(before=before, limit=100)
            if not batch:
                break
            enhanced.extend(batch)
            before = batch[-1].get("signature")
            t = batch[-1].get("timestamp")
            print(f"  enh {page+1} n={len(enhanced)} oldest={t}", flush=True)
            if t and times and t < min(times) - 200000:
                break
            if len(batch) < 100:
                break
            time.sleep(0.15)
    except Exception as e:
        print("enhanced fail", type(e), e, flush=True)
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
        for k in (tx.get("accountData") or []):
            pass

    # BPF / program accounts for top custom pids
    custom = [p for p, _ in programs.most_common() if p not in (
        "ComputeBudget111111111111111111111111111111",
        "11111111111111111111111111111111",
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    ) and not p.startswith("inner:")]
    prog_meta = []
    for pid in custom[:8]:
        try:
            body = rpc("getAccountInfo", [pid, {"encoding": "jsonParsed"}])
            val = (body.get("result") or {}).get("value") or {}
            parsed = ((val.get("data") or {}) if isinstance(val.get("data"), dict) else {}) 
            info = parsed.get("parsed", {}).get("info", {}) if isinstance(parsed, dict) else {}
            prog_meta.append(
                {
                    "pid": pid,
                    "owner": val.get("owner"),
                    "lamports": val.get("lamports"),
                    "executable": val.get("executable"),
                    "authority": info.get("authority") or info.get("upgradeAuthority"),
                    "programData": info.get("programData"),
                }
            )
            time.sleep(0.15)
        except Exception as e:
            prog_meta.append({"pid": pid, "error": str(e)})

    summary = {
        "wallet": WALLET,
        "n_signatures": len(sigs),
        "err_n": err_n,
        "err_rate": err_n / len(sigs) if sigs else None,
        "first_iso": datetime.fromtimestamp(min(times), tz=timezone.utc).isoformat() if times else None,
        "last_iso": datetime.fromtimestamp(max(times), tz=timezone.utc).isoformat() if times else None,
        "first_sig": sigs[-1]["signature"] if sigs else None,
        "last_sig": sigs[0]["signature"] if sigs else None,
        "sol_balance": json.loads((OUT / "summary_raw.json").read_text(encoding="utf-8")).get("sol_balance") if (OUT / "summary_raw.json").exists() else None,
        "trial": trial,
        "sample_n": len(samples),
        "programs": programs.most_common(25),
        "nonce_ix": nonce_n,
        "an225_ix": an225_n,
        "funding": funding,
        "cex": cex,
        "enhanced_inflows": inflows[:50],
        "program_accounts": prog_meta,
    }
    (OUT / "samples.json").write_text(json.dumps(samples, indent=2), encoding="utf-8")
    (OUT / "summary_raw.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "n_signatures", "err_n", "err_rate", "first_iso", "last_iso",
        "programs", "nonce_ix", "an225_ix", "program_accounts", "enhanced_inflows",
    )}, indent=2, default=str))


if __name__ == "__main__":
    main()
