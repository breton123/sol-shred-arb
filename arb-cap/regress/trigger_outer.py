#!/usr/bin/env python3
"""What actually moved the pool before each historical late DLMM→Pump winner.

Uses the slim block (outer+inner program ids, block order) to pick the
nearest preceding non-arb tx that touches DLMM or Pump, then getTransaction
jsonParsed for outer vs inner, pool accounts, and token deltas.
"""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
SLIM = ARB / "data" / "raw" / "helius_blocks" / "slim"
ALL = ROOT / "arb-cap" / "all_arbs_trial.jsonl"
FUNNEL = ROOT / "arb-cap" / "regress" / "hist_funnel.jsonl"
UNIV = ROOT / "arb-cap" / "regress" / "liveuniv_now.json"
CACHE = ROOT / "arb-cap" / "regress" / "tx_parsed"
OUT = ROOT / "arb-cap" / "regress" / "trigger_outer.jsonl"
YAML = ARB / "config" / "programs.yaml"

DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
INFRA = {
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
    "AddressLookupTab1e1111111111111111111111111",
}


def load_names() -> dict[str, tuple[str, str]]:
    names = {}
    for line in YAML.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("- {id:"):
            continue
        # - {id: ..., name: ..., kind: ...}
        try:
            body = line[line.index("{") + 1 : line.rindex("}")]
        except ValueError:
            continue
        parts = {}
        for bit in body.split(","):
            if ":" not in bit:
                continue
            k, v = bit.split(":", 1)
            parts[k.strip()] = v.strip().strip('"')
        if parts.get("id"):
            names[parts["id"]] = (parts.get("name") or parts["id"][:8], parts.get("kind") or "")
    return names


def rpc_url() -> str:
    path = ARB / "atomic_arbitrage" / "long_hop_analysis" / ".env"
    key = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("HELIUS_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit("no helius key")
    return "https://mainnet.helius-rpc.com/?api-key=" + key


def load_rows() -> list[dict]:
    rows = []
    for line in FUNNEL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def arb_sigs(slots: set[int]) -> dict[int, set[str]]:
    out: dict[int, set[str]] = defaultdict(set)
    with ALL.open(encoding="utf-8") as f:
        for line in f:
            if '"slot":' not in line:
                continue
            r = json.loads(line)
            s = r.get("slot")
            sig = r.get("signature")
            if s is None or not sig:
                continue
            s = int(s)
            if s in slots:
                out[s].add(sig)
    return out


def load_slim(slot: int) -> dict | None:
    p = SLIM / f"{slot}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def predecessor(block: dict, winner: str, arbs: set[str]) -> dict | None:
    txs = block.get("txs") or []
    idx = None
    for t in txs:
        if t.get("sig") == winner:
            idx = int(t["i"])
            break
    if idx is None:
        return None
    looked = 0
    for t in reversed(txs[:idx]):
        if t.get("kind") == "vote" or t.get("err"):
            continue
        looked += 1
        sig = t.get("sig")
        if sig in arbs:
            continue
        pids = t.get("pids") or []
        if DLMM in pids or PUMP in pids:
            return {
                "sig": sig,
                "i": int(t["i"]),
                "dist": idx - int(t["i"]),
                "pids": pids,
                "kind": t.get("kind"),
                "looked": looked,
            }
        if looked >= 80:
            break
    return None


def cache_path(sig: str) -> Path:
    return CACHE / sig[:2] / f"{sig}.json.gz"


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


def fetch_one(url: str, sig: str) -> tuple[str, dict | None]:
    if load_tx(sig) is not None:
        return sig, load_tx(sig)
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [sig, {
            "encoding": "jsonParsed",
            "maxSupportedTransactionVersion": 1,
            "commitment": "confirmed",
        }],
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    last = None
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                resp = json.loads(r.read().decode())
            if resp.get("error"):
                last = resp["error"]
                time.sleep(0.4 * (i + 1))
                continue
            result = resp.get("result")
            save_tx(sig, result or {})
            return sig, result
        except Exception as e:
            last = str(e)
            time.sleep(0.4 * (i + 1))
    save_tx(sig, {"_error": str(last)})
    return sig, None


def pk_of(key) -> str | None:
    if isinstance(key, str):
        return key
    if isinstance(key, dict):
        return key.get("pubkey")
    return None


def ix_pid(ix: dict) -> str | None:
    return ix.get("programId")


def ix_accounts(ix: dict) -> list[str]:
    accs = ix.get("accounts") or []
    out = []
    for a in accs:
        if isinstance(a, str):
            out.append(a)
        elif isinstance(a, dict) and a.get("pubkey"):
            out.append(a["pubkey"])
    return out


def analyze_tx(tx: dict, names: dict[str, tuple[str, str]]) -> dict:
    if not tx or tx.get("_error"):
        return {"ok": False}
    meta = tx.get("meta") or {}
    msg = (tx.get("transaction") or {}).get("message") or {}
    keys = [pk_of(k) for k in (msg.get("accountKeys") or [])]
    keys = [k for k in keys if k]
    outer = []
    for ix in msg.get("instructions") or []:
        pid = ix_pid(ix)
        if pid:
            outer.append((pid, ix_accounts(ix)))
    inner = []
    for group in meta.get("innerInstructions") or []:
        for ix in group.get("instructions") or []:
            pid = ix_pid(ix)
            if pid:
                inner.append((pid, ix_accounts(ix)))
    def label(pid: str) -> str:
        if pid in names:
            return names[pid][0]
        return pid[:8] + "…"

    outer_pids = []
    seen = set()
    for pid, _ in outer:
        if pid not in seen:
            seen.add(pid)
            outer_pids.append(pid)
    inner_pids = []
    seen_i = set()
    for pid, _ in inner:
        if pid not in seen_i:
            seen_i.add(pid)
            inner_pids.append(pid)
    venue_outer = [p for p in outer_pids if p not in INFRA]
    dlmm_ix = [(where, acc) for where, rows in (("outer", outer), ("inner", inner)) for pid, acc in rows if pid == DLMM]
    pump_ix = [(where, acc) for where, rows in (("outer", outer), ("inner", inner)) for pid, acc in rows if pid == PUMP]
    dlmm_pools = []
    pump_pools = []
    for where, acc in dlmm_ix:
        if acc:
            dlmm_pools.append({"where": where, "pool": acc[0]})
    for where, acc in pump_ix:
        if acc:
            pump_pools.append({"where": where, "pool": acc[0]})

    deltas = []
    pre = {(b.get("accountIndex"), b.get("mint")): b for b in (meta.get("preTokenBalances") or [])}
    post = {(b.get("accountIndex"), b.get("mint")): b for b in (meta.get("postTokenBalances") or [])}
    for k in set(pre) | set(post):
        a = pre.get(k) or {}
        z = post.get(k) or {}
        try:
            before = int(((a.get("uiTokenAmount") or {}).get("amount")) or 0)
            after = int(((z.get("uiTokenAmount") or {}).get("amount")) or 0)
        except ValueError:
            continue
        if before == after:
            continue
        src = z or a
        idx = src.get("accountIndex")
        acct = keys[idx] if isinstance(idx, int) and idx < len(keys) else None
        deltas.append({
            "mint": k[1],
            "owner": src.get("owner"),
            "account": acct,
            "delta": after - before,
        })
    deltas.sort(key=lambda d: -abs(d["delta"]))
    if not venue_outer:
        primary = "(infra only)"
    elif len(venue_outer) == 1:
        primary = label(venue_outer[0])
    else:
        primary = " + ".join(label(p) for p in venue_outer)
    shape = "no DLMM/Pump"
    has_dlmm = bool(dlmm_ix)
    has_pump = bool(pump_ix)
    dlmm_outer = any(w == "outer" for w, _ in dlmm_ix)
    pump_outer = any(w == "outer" for w, _ in pump_ix)
    if dlmm_outer and not pump_outer and not any(p not in (DLMM, PUMP) and p not in INFRA for p in outer_pids):
        shape = "direct DLMM"
    elif pump_outer and not dlmm_outer and not any(p not in (DLMM, PUMP) and p not in INFRA for p in outer_pids):
        shape = "direct Pump"
    elif dlmm_outer or pump_outer:
        shape = "outer DEX"
        if any(p not in (DLMM, PUMP) and p not in INFRA for p in outer_pids):
            shape = "outer DEX + other"
    elif has_dlmm or has_pump:
        shape = "CPI into DEX"
    return {
        "ok": True,
        "outer": [label(p) for p in outer_pids],
        "outer_ids": outer_pids,
        "inner": [label(p) for p in inner_pids if p not in INFRA],
        "venue_outer": [label(p) for p in venue_outer],
        "primary": primary,
        "primary_id": venue_outer[0] if len(venue_outer) == 1 else None,
        "shape": shape,
        "dlmm_pools": dlmm_pools,
        "pump_pools": pump_pools,
        "n_token_deltas": len(deltas),
        "top_deltas": deltas[:6],
        "n_keys": len(keys),
    }


def table(rows: list[dict], key: str) -> list[tuple]:
    acc = defaultdict(lambda: [0, 0.0])
    for r in rows:
        acc[r.get(key) or "?"][0] += 1
        acc[r.get(key) or "?"][1] += float(r.get("profit") or 0)
    return sorted(acc.items(), key=lambda kv: -kv[1][1])


def emit(title: str, rows: list[dict], key: str) -> None:
    print(f"\n{title}  n={len(rows)}  ${sum(r['profit'] for r in rows):.1f}")
    print(f"{'trigger':<42} {'races':>6} {'$':>10}")
    for name, (n, usd) in table(rows, key):
        print(f"{name:<42} {n:6} {usd:10.1f}")


def main() -> int:
    names = load_names()
    rows = load_rows()
    slots = {int(r["slot"]) for r in rows}
    print(f"rows={len(rows)} slots={len(slots)} loading arb sigs", flush=True)
    by_slot = arb_sigs(slots)
    url = rpc_url()
    pending = []
    chosen = []
    for r in rows:
        block = load_slim(int(r["slot"]))
        pred = predecessor(block, r["sig"], by_slot.get(int(r["slot"]), set())) if block else None
        rec = {
            "cohort": r["cohort"],
            "frame_why": r["frame_why"],
            "profit": r["profit"],
            "slot": r["slot"],
            "winner": r["sig"],
            "old_trigger": r.get("trigger_sig"),
            "pred": pred,
        }
        chosen.append(rec)
        if pred and pred.get("sig"):
            pending.append(pred["sig"])
    need = [s for s in dict.fromkeys(pending) if load_tx(s) is None]
    print(f"predecessors={len(pending)} unique={len(set(pending))} fetch={len(need)}", flush=True)
    if need:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(fetch_one, url, s) for s in need]
            done = 0
            for fut in as_completed(futs):
                fut.result()
                done += 1
                if done % 20 == 0:
                    print(f"  fetched {done}/{len(need)}", flush=True)
    univ = {p["pubkey"] for p in json.loads(UNIV.read_text(encoding="utf-8")).get("pools") or []}
    scored = []
    for rec in chosen:
        pred = rec["pred"] or {}
        tx = load_tx(pred["sig"]) if pred.get("sig") else None
        info = analyze_tx(tx, names) if tx else {"ok": False}
        pools = [p["pool"] for p in info.get("dlmm_pools") or []] + [p["pool"] for p in info.get("pump_pools") or []]
        scored.append({
            **{k: rec[k] for k in ("cohort", "frame_why", "profit", "slot", "winner", "old_trigger")},
            "found": bool(pred),
            "same_as_old": pred.get("sig") == rec.get("old_trigger") if pred else False,
            "dist": pred.get("dist"),
            "pred_sig": pred.get("sig"),
            "primary": info.get("primary"),
            "shape": info.get("shape"),
            "outer": info.get("outer"),
            "inner": info.get("inner"),
            "dlmm_pools": info.get("dlmm_pools"),
            "pump_pools": info.get("pump_pools"),
            "in_universe": sorted({p for p in pools if p in univ}),
            "top_deltas": info.get("top_deltas"),
            "ok": info.get("ok", False),
        })
    OUT.write_text("".join(json.dumps(r) + "\n" for r in scored), encoding="utf-8")
    late = [r for r in scored if r["cohort"] == "late121"]
    nodex = [r for r in late if r["frame_why"] == "no_dex_bytes"]
    jack = [r for r in scored if r["profit"] >= 50]
    big = [r for r in scored if abs(r["profit"] - 385.3866839532803) < 0.01 or r["profit"] > 380]
    emit("LATE 121 — outer program of the preceding DLMM/Pump tx", late, "primary")
    emit("LATE 121 — shape", late, "shape")
    emit("NO-DEX-OUTER BUCKET — outer program", nodex, "primary")
    emit("NO-DEX-OUTER BUCKET — shape", nodex, "shape")
    emit("JACKPOTS ≥$50 — outer program", jack, "primary")
    miss = sum(1 for r in late if not r["found"])
    same = sum(1 for r in late if r["same_as_old"])
    cpi = [r for r in late if r["shape"] == "CPI into DEX"]
    uni = [r for r in late if r["in_universe"]]
    print(f"\nlate predecessor found {len(late)-miss}/{len(late)}  same as old trigger {same}/{len(late)}")
    print(f"CPI into DEX {len(cpi)} ${sum(r['profit'] for r in cpi):.1f}")
    print(f"pool account in current 171 {len(uni)} ${sum(r['profit'] for r in uni):.1f}")
    print("\n$385 / largest")
    for r in sorted(big or jack, key=lambda x: -x["profit"])[:3]:
        print(json.dumps({k: r[k] for k in (
            "profit", "shape", "primary", "outer", "inner", "dist", "same_as_old",
            "dlmm_pools", "pump_pools", "in_universe", "top_deltas", "frame_why",
        )}, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
