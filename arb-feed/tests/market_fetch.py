#!/usr/bin/env python3
"""Full-window SHRED_V1_MARKET fetch. Resume-safe. Does not touch raw .cap."""
from __future__ import annotations

import argparse
import asyncio
import base64
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
sys.path.insert(0, str(ARB))

from dataset.helius import fetch_slim_blocks, load_slim_block, _rpc  # noqa: E402
from dataset.env import helius_rpc_url  # noqa: E402
from dataset.registry import load_registry  # noqa: E402
from dataset.trigger_distance import INFRA, _interesting  # noqa: E402

OUT = ROOT / "arb-cap" / "shred_v1"
TX_DIR = ROOT / "arb-cap" / "cap004" / "tx"
ALL_JSONL = ROOT / "arb-cap" / "all_arbs_trial.jsonl"

PROG_DLMM = bytes(
    [
        0x04, 0xE9, 0xE1, 0x2F, 0xBC, 0x84, 0xE8, 0x26,
        0xC9, 0x32, 0xCC, 0xE9, 0xE2, 0x64, 0x0C, 0xCE,
        0x15, 0x59, 0x0C, 0x1C, 0x62, 0x73, 0xB0, 0x92,
        0x57, 0x08, 0xBA, 0x3B, 0x85, 0x20, 0xB0, 0xBC,
    ]
)
PROG_PUMP = bytes(
    [
        0x0C, 0x14, 0xDE, 0xFC, 0x82, 0x5E, 0xC6, 0x76,
        0x94, 0x25, 0x08, 0x18, 0xBB, 0x65, 0x40, 0x65,
        0xF4, 0x29, 0x8D, 0x31, 0x56, 0xD5, 0x71, 0xB4,
        0xD4, 0xF8, 0x09, 0x0C, 0x18, 0xE9, 0xA8, 0x63,
    ]
)


def b58decode(s: str) -> bytes:
    alph = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in s:
        n = n * 58 + alph.index(c)
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    h = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + h


def b58_32(s: str) -> bytes:
    raw = b58decode(s)
    return raw[-32:] if len(raw) >= 32 else raw.rjust(32, b"\x00")


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def tx_cache_path(sig: str) -> Path:
    return TX_DIR / sig[:2] / f"{sig}.json.gz"


def load_tx(sig: str) -> dict | None:
    p = tx_cache_path(sig)
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def save_tx(sig: str, obj: dict) -> None:
    p = tx_cache_path(sig)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp.gz")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f)
    tmp.replace(p)


def find_trigger(slim: dict, searcher_sig: str, slot_arb_sigs: set[str], dex_ids, router_ids):
    txs = slim.get("txs") or []
    by_sig = {t.get("sig"): t for t in txs if t.get("sig")}
    me = by_sig.get(searcher_sig)
    if not me:
        return None
    first_i = int(me["i"])
    arb_pids = _interesting(me.get("pids") or [], dex_ids, router_ids)
    known = dex_ids | router_ids
    match_pids = {p for p in arb_pids if p in known}
    looked = 0
    trigger = None
    confidence = "none"
    for t in reversed(txs[:first_i]):
        if t.get("kind") == "vote":
            continue
        looked += 1
        if t.get("err"):
            continue
        sig = t.get("sig")
        if sig in slot_arb_sigs:
            continue
        interesting = _interesting(t.get("pids") or [], dex_ids, router_ids)
        if not interesting:
            continue
        overlap = interesting & match_pids if match_pids else set()
        known_hit = interesting & known
        if overlap & known:
            confidence = "high"
            trigger = t
            break
        if overlap or known_hit:
            confidence = "medium"
            trigger = t
            break
        if looked >= 80:
            confidence = "low"
            trigger = t
            break
    if trigger is None:
        return None
    return {
        "trigger_sig": trigger.get("sig"),
        "trigger_i": int(trigger["i"]),
        "trigger_kind": trigger.get("kind"),
        "mriya_i": first_i,
        "dist": first_i - int(trigger["i"]),
        "confidence": confidence,
    }


def cu16(p: bytes, off: int):
    b0 = p[off]
    if b0 < 0x80:
        return b0, off + 1
    b1 = p[off + 1]
    if b1 < 0x80:
        return (b0 & 0x7F) | (b1 << 7), off + 2
    b2 = p[off + 2]
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


def actionable_offset(raw: bytes, infra_b: set[bytes]) -> dict:
    out = {"ok": False, "off": None, "proto": None}
    if not raw or len(raw) < 80:
        return out
    try:
        nsig, off = cu16(raw, 0)
        if nsig == 0 or nsig > 64:
            return out
        off += nsig * 64
        if off >= len(raw):
            return out
        if raw[off] & 0x80:
            off += 2
        else:
            off += 1
        off += 2
        nkeys, off = cu16(raw, off)
        keys = off
        off += nkeys * 32 + 32
        ninstr, off = cu16(raw, off)
        best = None
        proto = None
        for _ in range(ninstr):
            pi = raw[off]
            off += 1
            nacc, off = cu16(raw, off)
            accs = raw[off : off + nacc]
            off += nacc
            dlen, off = cu16(raw, off)
            data_off = off
            off += dlen
            if pi >= nkeys:
                continue
            pid = raw[keys + pi * 32 : keys + pi * 32 + 32]
            if pid in infra_b:
                continue
            need = [keys + pi * 32 + 32]
            if accs and accs[0] < nkeys:
                need.append(keys + accs[0] * 32 + 32)
            need.append(data_off + min(dlen, 16))
            end = max(need)
            if pid == PROG_DLMM:
                proto, best = "dlmm", end
                break
            if pid == PROG_PUMP:
                proto, best = "pump", end
                break
            if best is None:
                proto, best = "other", end
        if best is None:
            out["off"] = len(raw)
            out["proto"] = "unknown"
            out["ok"] = True
            return out
        out["off"] = best
        out["proto"] = proto
        out["ok"] = True
        return out
    except Exception:
        out["off"] = len(raw)
        out["ok"] = False
        return out


async def fetch_base64(sigs: list[str], workers: int = 10):
    import aiohttp

    url = helius_rpc_url()
    todo = []
    for s in sigs:
        obj = load_tx(s)
        if obj is None or not obj.get("raw_b64"):
            todo.append(s)
    print(f"getTransaction base64 {len(sigs)} unique, new={len(todo)}", flush=True)
    if not todo:
        return
    sem = asyncio.Semaphore(workers)
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(todo), workers):
            chunk = todo[i : i + workers]

            async def one(sig):
                body = await _rpc(
                    session,
                    url,
                    "getTransaction",
                    [
                        sig,
                        {
                            "encoding": "base64",
                            "maxSupportedTransactionVersion": 1,
                            "commitment": "confirmed",
                        },
                    ],
                    sem,
                )
                return sig, body

            results = await asyncio.gather(*[one(s) for s in chunk])
            for sig, body in results:
                res = (body or {}).get("result") or {}
                tx = res.get("transaction")
                raw_b64 = None
                if isinstance(tx, list) and tx:
                    raw_b64 = tx[0]
                save_tx(
                    sig,
                    {
                        "signature": sig,
                        "raw_b64": raw_b64,
                        "slot": res.get("slot"),
                        "error": (body or {}).get("error"),
                    },
                )
            if (i // workers) % 20 == 0:
                print(f"  tx {i + len(chunk)}/{len(todo)}", flush=True)
            await asyncio.sleep(0.05)


def raw_bytes(sig: str) -> bytes | None:
    obj = load_tx(sig)
    if not obj or not obj.get("raw_b64"):
        return None
    try:
        return base64.b64decode(obj["raw_b64"])
    except Exception:
        return None


def infra_set() -> set[bytes]:
    return {
        b58_32("11111111111111111111111111111111"),
        b58_32("ComputeBudget111111111111111111111111111111"),
        b58_32("Vote111111111111111111111111111111111111111"),
        b58_32("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
        b58_32("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"),
        b58_32("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"),
        b58_32("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"),
        b58_32("AddressLookupTab1e1111111111111111111111111"),
        b58_32("Sysvar1nstructions1111111111111111111111111"),
        b58_32("Ed25519SigVerify111111111111111111111111111"),
    }


def phase_slim(rows: list[dict]):
    slots = sorted({int(r["slot"]) for r in rows if r.get("slot") is not None})
    print(f"unique slots {len(slots)}", flush=True)
    stats = asyncio.run(fetch_slim_blocks(slots, workers=16, rate_limit=20.0))
    print("slim", stats, flush=True)


def phase_triggers(rows: list[dict]) -> list[dict]:
    slot_arbs: dict[int, set[str]] = defaultdict(set)
    for r in rows:
        if r.get("slot") is not None and r.get("signature"):
            slot_arbs[int(r["slot"])].add(r["signature"])
    reg = load_registry()
    dex_ids, router_ids = set(), set()
    for pid, row in (reg.get("by_id") or {}).items():
        if row.get("kind") in ("dex", "clob"):
            dex_ids.add(pid)
        elif row.get("kind") == "router":
            router_ids.add(pid)
    pairs = []
    miss_block = miss_trig = 0
    for i, r in enumerate(rows):
        slot = int(r["slot"])
        sig = r["signature"]
        slim = load_slim_block(slot)
        if not slim or not slim.get("txs"):
            miss_block += 1
            pairs.append({**r, "pair_ok": False, "why": "no_slim"})
            continue
        got = find_trigger(slim, sig, slot_arbs.get(slot, set()), dex_ids, router_ids)
        if not got:
            miss_trig += 1
            pairs.append({**r, "pair_ok": False, "why": "no_trigger"})
            continue
        pairs.append({**r, "pair_ok": True, **got})
        if (i + 1) % 20000 == 0:
            print(f"  trigger {i+1}/{len(rows)}", flush=True)
    dest = OUT / "triggers.jsonl"
    with dest.open("w", encoding="utf-8") as f:
        for p in pairs:
            rec = {
                "user": p.get("user"),
                "signature": p.get("signature"),
                "slot": p.get("slot"),
                "tick": p.get("tick_index"),
                "dexes": p.get("dexes"),
                "hops": p.get("number_of_swap_steps"),
                "profit": p.get("pure_profit"),
                "provider": p.get("provider"),
                "leader": p.get("validator_name"),
                "city": p.get("validator_city"),
                "tip": p.get("tip"),
                "prio": p.get("priority_fee_usd"),
                "pair_ok": bool(p.get("pair_ok")),
                "why": p.get("why"),
                "trigger_sig": p.get("trigger_sig"),
                "trigger_i": p.get("trigger_i"),
                "mriya_i": p.get("mriya_i"),
                "dist": p.get("dist"),
                "confidence": p.get("confidence"),
                "trigger_kind": p.get("trigger_kind"),
                "immediate": bool(p.get("pair_ok") and p.get("dist") is not None and p["dist"] <= 2),
            }
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    print(
        f"triggers ok={sum(1 for p in pairs if p.get('pair_ok'))} "
        f"miss_block={miss_block} miss_trig={miss_trig} wrote {dest}",
        flush=True,
    )
    return pairs


def phase_txs_and_pairs(pairs: list[dict] | None):
    if pairs is None:
        pairs = []
        for line in (OUT / "triggers.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                pairs.append(json.loads(line))
    need = []
    for p in pairs:
        if p.get("trigger_sig"):
            need.append(p["trigger_sig"])
    asyncio.run(fetch_base64(sorted(set(need)), workers=10))
    infra_b = infra_set()
    dest = OUT / "pairs.jsonl"
    n_ok = n_imm = n_hex = 0
    with dest.open("w", encoding="utf-8") as f:
        for p in pairs:
            sig = p.get("signature") or p.get("mriya_sig")
            rec = {
                "user": p.get("user"),
                "mriya_sig": sig,
                "slot": p.get("slot"),
                "tick": p.get("tick"),
                "dexes": p.get("dexes"),
                "hops": p.get("hops"),
                "profit": p.get("profit"),
                "provider": p.get("provider"),
                "leader": p.get("leader"),
                "city": p.get("city"),
                "tip": p.get("tip"),
                "prio": p.get("prio"),
                "pair_ok": bool(p.get("pair_ok")),
                "why": p.get("why"),
                "trigger_sig": p.get("trigger_sig"),
                "trigger_i": p.get("trigger_i"),
                "mriya_i": p.get("mriya_i"),
                "dist": p.get("dist"),
                "confidence": p.get("confidence"),
                "immediate": bool(p.get("immediate")),
            }
            rec["mriya_tx_hex"] = ""
            rec["mriya_sig_hex"] = b58decode(sig).hex() if sig else ""
            rec["trigger_sig_hex"] = b58decode(p["trigger_sig"]).hex() if p.get("trigger_sig") else ""
            tt = raw_bytes(p["trigger_sig"]) if p.get("trigger_sig") else None
            rec["trigger_tx_hex"] = tt.hex() if tt else ""
            rec["trigger_tx_len"] = len(tt) if tt else 0
            if tt:
                n_hex += 1
                act = actionable_offset(tt, infra_b)
                rec["actionable_off"] = act.get("off")
                rec["actionable_proto"] = act.get("proto")
                rec["actionable_ok"] = act.get("ok")
            else:
                rec["actionable_off"] = None
                rec["actionable_proto"] = None
                rec["actionable_ok"] = False
            if rec["pair_ok"]:
                n_ok += 1
            if rec["immediate"]:
                n_imm += 1
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
    print(f"wrote {dest} n={len(pairs)} ok={n_ok} immediate={n_imm} trig_hex={n_hex}", flush=True)


def _use_out(p: Path) -> None:
    global OUT
    OUT = p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["slim", "triggers", "txs", "all"], default="all")
    ap.add_argument("--min-profit", type=float, default=0.0)
    ap.add_argument("--cached-slim-only", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    dest = Path(args.out) if args.out else Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\shred_v1")
    _use_out(dest)
    dest.mkdir(parents=True, exist_ok=True)
    TX_DIR.mkdir(parents=True, exist_ok=True)
    print("load arbs...", flush=True)
    rows = load_rows(ALL_JSONL)
    if args.min_profit:
        rows = [r for r in rows if float(r.get("pure_profit") or 0) >= args.min_profit]
    if args.cached_slim_only:
        keep = []
        for r in rows:
            if r.get("slot") is None:
                continue
            b = load_slim_block(int(r["slot"]))
            if b and b.get("txs"):
                keep.append(r)
        rows = keep
    print(f"rows {len(rows)}", flush=True)
    if args.phase in ("slim", "all"):
        phase_slim(rows)
    if args.phase in ("triggers", "all"):
        pairs = phase_triggers(rows)
    else:
        pairs = None
    if args.phase in ("txs", "all"):
        phase_txs_and_pairs(pairs)


if __name__ == "__main__":
    main()
