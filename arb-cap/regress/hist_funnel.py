#!/usr/bin/env python3
"""Replay CAP-004/005 known winners through current CORE-010 + universe gates.

Does not quote. Historical DLMM bins are not in this corpus, so the
state/PnL stages are reported as not evaluated.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
RACES = ROOT / "arb-cap" / "cap005_late" / "races.jsonl"
PAIR_FILES = [
    ROOT / "arb-cap" / "cap004_s25" / "pairs.jsonl",
    ROOT / "arb-cap" / "cap004" / "pairs.jsonl",
    ROOT / "arb-cap" / "shred_v1_fat" / "pairs.jsonl",
]
UNIV = ROOT / "arb-cap" / "regress" / "liveuniv_now.json"
SOL = "So11111111111111111111111111111111111111112"

PROG_DLMM = bytes([
    0x04, 0xE9, 0xE1, 0x2F, 0xBC, 0x84, 0xE8, 0x26,
    0xC9, 0x32, 0xCC, 0xE9, 0xE2, 0x64, 0x0C, 0xCE,
    0x15, 0x59, 0x0C, 0x1C, 0x62, 0x73, 0xB0, 0x92,
    0x57, 0x08, 0xBA, 0x3B, 0x85, 0x20, 0xB0, 0xBC,
])
PROG_PUMP = bytes([
    0x0C, 0x14, 0xDE, 0xFC, 0x82, 0x5E, 0xC6, 0x76,
    0x94, 0x25, 0x08, 0x18, 0xBB, 0x65, 0x40, 0x65,
    0xF4, 0x29, 0x8D, 0x31, 0x56, 0xD5, 0x71, 0xB4,
    0xD4, 0xF8, 0x09, 0x0C, 0x18, 0xE9, 0xA8, 0x63,
])
DLMM_SWAP2 = bytes([0x41, 0x4B, 0x3F, 0x4C, 0xEB, 0x5B, 0x5B, 0x88])
DLMM_SWAP1 = bytes([0xF8, 0xC6, 0x9E, 0x91, 0xE1, 0x75, 0x87, 0xC8])
PUMP_BUY = bytes([0x66, 0x06, 0x3D, 0x12, 0x01, 0xDA, 0xEB, 0xEA])
PUMP_SELL = bytes([0x33, 0xE6, 0x85, 0xA4, 0x01, 0x7F, 0x83, 0xAD])
PUMP_BUY_EQ = bytes([0xC6, 0x2E, 0x15, 0x52, 0xB4, 0xD9, 0xE8, 0x70])
TX_SIG_MAX = 12
TX_KEY_MAX = 64
TX_INSTR_MAX = 64
LAMPORTS = 1_000_000_000


def cu16(b: bytes, off: int):
    if off >= len(b):
        return None
    b0 = b[off]
    if (b0 & 0x80) == 0:
        return b0, off + 1
    if off + 1 >= len(b):
        return None
    b1 = b[off + 1]
    if (b1 & 0x80) == 0:
        if b1 == 0:
            return "bad"
        return (b0 & 0x7F) | (b1 << 7), off + 2
    if off + 2 >= len(b):
        return None
    b2 = b[off + 2]
    if (b2 & 0xFC) != 0 or b2 == 0:
        return "bad"
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


def b58(raw: bytes) -> str:
    alph = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alph[r] + out
    pad = 0
    for byte in raw:
        if byte == 0:
            pad += 1
        else:
            break
    return "1" * pad + (out or "1")


def parse_tx(raw: bytes) -> dict:
    """CORE-010 frame_try_at at offset 0, plus outer swapix pool extraction.

    Address-lookup accounts are not resolved. An index past the static key
    table is the same thing swapix rejects.
    """
    out = {
        "klass": "absent",
        "why": "no bytes",
        "pools": [],
        "outer_dex": False,
        "dex_key_present": False,
        "nkeys": 0,
        "nsig": 0,
    }
    if not raw:
        return out
    if PROG_DLMM in raw or PROG_PUMP in raw:
        out["dex_key_present"] = True
    got = cu16(raw, 0)
    if got is None:
        out["klass"] = "incomplete"
        out["why"] = "truncated_nsig"
        return out
    if got == "bad":
        out["klass"] = "invalid"
        out["why"] = "bad_nsig"
        return out
    nsig, off = got
    out["nsig"] = nsig
    if nsig < 1 or nsig > TX_SIG_MAX:
        out["klass"] = "invalid"
        out["why"] = "nsig_range"
        return out
    if off + nsig * 64 > len(raw):
        out["klass"] = "incomplete"
        out["why"] = "truncated_sigs"
        return out
    off += nsig * 64
    if off >= len(raw):
        out["klass"] = "incomplete"
        out["why"] = "truncated_header"
        return out
    b0 = raw[off]
    off += 1
    versioned = 0
    if b0 & 0x80:
        if (b0 & 0x7F) != 0:
            out["klass"] = "invalid"
            out["why"] = "bad_version"
            return out
        versioned = 1
        if off >= len(raw):
            out["klass"] = "incomplete"
            out["why"] = "truncated_version"
            return out
        if raw[off] != nsig:
            out["klass"] = "invalid"
            out["why"] = "nsig_mismatch"
            return out
        off += 1
    elif b0 != nsig:
        out["klass"] = "invalid"
        out["why"] = "nsig_mismatch"
        return out
    if off + 2 > len(raw):
        out["klass"] = "incomplete"
        out["why"] = "truncated_header"
        return out
    ro_s = raw[off]
    ro_u = raw[off + 1]
    off += 2
    got = cu16(raw, off)
    if got is None:
        out["klass"] = "incomplete"
        out["why"] = "truncated_nkeys"
        return out
    if got == "bad":
        out["klass"] = "invalid"
        out["why"] = "bad_nkeys"
        return out
    nkeys, off = got
    out["nkeys"] = nkeys
    if ro_s >= nsig or nkeys < nsig or nkeys > TX_KEY_MAX or nsig + ro_u > nkeys:
        out["klass"] = "invalid"
        out["why"] = "header" if nkeys <= TX_KEY_MAX else "nkeys_gt_64"
        if nkeys > TX_KEY_MAX:
            out["why"] = "nkeys_gt_64"
        return out
    if off + nkeys * 32 + 32 > len(raw):
        out["klass"] = "incomplete"
        out["why"] = "truncated_keys"
        return out
    keys = [raw[off + i * 32: off + (i + 1) * 32] for i in range(nkeys)]
    off += nkeys * 32 + 32
    got = cu16(raw, off)
    if got is None:
        out["klass"] = "incomplete"
        out["why"] = "truncated_ninstr"
        return out
    if got == "bad":
        out["klass"] = "invalid"
        out["why"] = "bad_ninstr"
        return out
    ninstr, off = got
    if ninstr == 0 or ninstr > TX_INSTR_MAX:
        out["klass"] = "invalid"
        out["why"] = "ninstr_range"
        return out
    have_dex = False
    pools = []
    for _ in range(ninstr):
        if off >= len(raw):
            out["klass"] = "incomplete"
            out["why"] = "truncated_ix"
            return out
        prog_idx = raw[off]
        off += 1
        if prog_idx >= nkeys:
            out["klass"] = "invalid"
            out["why"] = "prog_idx_alt_or_oob"
            return out
        pkey = keys[prog_idx]
        proto = None
        if pkey == PROG_DLMM:
            proto = "dlmm"
            have_dex = True
        elif pkey == PROG_PUMP:
            proto = "pump"
            have_dex = True
        got = cu16(raw, off)
        if got is None:
            out["klass"] = "incomplete"
            out["why"] = "truncated_ix"
            return out
        if got == "bad":
            out["klass"] = "invalid"
            out["why"] = "bad_nacct"
            return out
        nacct, off = got
        if nacct > 255 or off + nacct > len(raw):
            if off + nacct > len(raw):
                out["klass"] = "incomplete"
                out["why"] = "truncated_ix"
                return out
            out["klass"] = "invalid"
            out["why"] = "nacct"
            return out
        acc = raw[off: off + nacct]
        off += nacct
        got = cu16(raw, off)
        if got is None:
            out["klass"] = "incomplete"
            out["why"] = "truncated_ix"
            return out
        if got == "bad":
            out["klass"] = "invalid"
            out["why"] = "bad_dlen"
            return out
        dlen, off = got
        if off + dlen > len(raw):
            out["klass"] = "incomplete"
            out["why"] = "truncated_ix"
            return out
        data = raw[off: off + dlen]
        off += dlen
        if proto is None or nacct < 1 or dlen < 24:
            continue
        disc = data[:8]
        if proto == "dlmm" and disc not in (DLMM_SWAP2, DLMM_SWAP1):
            continue
        if proto == "pump" and disc == PUMP_BUY:
            pools.append({"proto": proto, "why": "pump_exact_out", "pk": None, "amount": 0})
            continue
        if proto == "pump" and disc not in (PUMP_SELL, PUMP_BUY_EQ):
            continue
        amount = int.from_bytes(data[8:16], "little")
        if amount == 0:
            continue
        pool_i = acc[0]
        if pool_i >= nkeys:
            pools.append({"proto": proto, "why": "pool_in_alt", "pk": None, "amount": amount})
            continue
        dir_static = True
        if proto == "dlmm":
            if nacct < 11:
                dir_static = False
            else:
                for idx in (4, 6, 7, 10):
                    if acc[idx] >= nkeys:
                        dir_static = False
        pools.append({
            "proto": proto,
            "why": "static" if dir_static else "dir_accounts_in_alt",
            "pk": b58(keys[pool_i]),
            "amount": amount,
        })
    if versioned:
        got = cu16(raw, off)
        if got is None:
            out["klass"] = "incomplete"
            out["why"] = "truncated_alt"
            return out
        if got == "bad":
            out["klass"] = "invalid"
            out["why"] = "bad_alt"
            return out
        nlut, off = got
        if nlut > 32:
            out["klass"] = "invalid"
            out["why"] = "nlut"
            return out
        for _ in range(nlut):
            if off + 32 > len(raw):
                out["klass"] = "incomplete"
                out["why"] = "truncated_alt"
                return out
            off += 32
            for _w in range(2):
                got = cu16(raw, off)
                if got is None:
                    out["klass"] = "incomplete"
                    out["why"] = "truncated_alt"
                    return out
                if got == "bad":
                    out["klass"] = "invalid"
                    out["why"] = "bad_alt"
                    return out
                nw, off = got
                if off + nw > len(raw):
                    out["klass"] = "incomplete"
                    out["why"] = "truncated_alt"
                    return out
                off += nw
    out["outer_dex"] = have_dex
    out["pools"] = pools
    if not have_dex:
        out["klass"] = "invalid"
        out["why"] = "no_outer_dex" if out["dex_key_present"] else "no_dex_bytes"
        return out
    out["klass"] = "framed"
    out["why"] = "outer_dlmm_or_pump"
    return out


def load_univ(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    by = {}
    for p in doc.get("pools") or []:
        by[p["pubkey"]] = p
    return by


def partner_kind(pool: dict, univ: dict[str, dict]) -> str | None:
    if pool.get("proto") not in ("dlmm", "pump"):
        return None
    mx, my = pool.get("mx"), pool.get("my")
    if not mx or not my:
        return None
    route0 = False
    fam5 = False
    for other in univ.values():
        if other.get("pubkey") == pool.get("pubkey"):
            continue
        if {pool.get("proto"), other.get("proto")} != {"dlmm", "pump"}:
            continue
        d = pool if pool.get("proto") == "dlmm" else other
        u = other if pool.get("proto") == "dlmm" else pool
        if d.get("my") == SOL and u.get("my") == SOL and d.get("mx") == u.get("mx") and d.get("mx") != SOL:
            route0 = True
            continue
        def tok(q):
            if q.get("mx") == SOL and q.get("my") != SOL:
                return q.get("my")
            if q.get("my") == SOL and q.get("mx") != SOL:
                return q.get("mx")
            return None
        if tok(pool) and tok(pool) == tok(other):
            fam5 = True
    if route0:
        return "route0"
    if fam5:
        return "fam5"
    return None


def first_static(parsed: dict) -> dict | None:
    for p in parsed["pools"]:
        if p.get("pk") and p.get("why") in ("static", "dir_accounts_in_alt"):
            return p
    return None


def sol_clip(amount: int) -> float | None:
    if amount <= 0:
        return None
    sol = amount / LAMPORTS
    if 0.001 <= sol <= 500:
        return sol
    return None


def load_races() -> list[dict]:
    rows = []
    for line in RACES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("supported") and r.get("route") == "Meteora DLMM → Pump Swap":
            r["cohort"] = "late121"
            rows.append(r)
    return rows


def attach_hex(rows: list[dict]) -> None:
    want = {r["sig"] for r in rows}
    found: dict[str, dict] = {}
    key = '"mriya_sig":"'
    for path in PAIR_FILES:
        if not path.exists() or len(found) == len(want):
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                i = line.find(key)
                if i < 0:
                    continue
                j = line.find('"', i + len(key))
                sig = line[i + len(key): j]
                if sig not in want or sig in found:
                    continue
                found[sig] = json.loads(line)
                if len(found) == len(want):
                    break
    for r in rows:
        p = found.get(r["sig"]) or {}
        r["trigger_tx_hex"] = p.get("trigger_tx_hex") or ""
        r["winner_tx_hex"] = p.get("mriya_tx_hex") or ""
        r["pair_hit"] = bool(p)


def add_jackpot(rows: list[dict]) -> list[dict]:
    have = {r["sig"] for r in rows}
    extra = []
    path = ROOT / "arb-cap" / "shred_v1_fat" / "pairs.jsonl"
    with path.open(encoding="utf-8") as f:
        for line in f:
            if '"Meteora DLMM","Pump Swap"' not in line and '"Meteora DLMM", "Pump Swap"' not in line:
                continue
            rec = json.loads(line)
            dexes = rec.get("dexes") or []
            if dexes != ["Meteora DLMM", "Pump Swap"]:
                continue
            if float(rec.get("profit") or 0) < 50:
                continue
            sig = rec.get("mriya_sig")
            if not sig or sig in have:
                continue
            extra.append({
                "sig": sig,
                "trigger_sig": rec.get("trigger_sig"),
                "slot": rec.get("slot"),
                "user": rec.get("user"),
                "profit": float(rec.get("profit") or 0),
                "route": "Meteora DLMM → Pump Swap",
                "act_us": None,
                "cohort": "jackpot_outside_121",
                "supported": True,
                "trigger_tx_hex": rec.get("trigger_tx_hex") or "",
                "winner_tx_hex": rec.get("mriya_tx_hex") or "",
                "pair_hit": True,
            })
    return rows + extra


def score(rows: list[dict], univ: dict[str, dict]) -> list[dict]:
    scored = []
    for r in rows:
        trig = parse_tx(bytes.fromhex(r["trigger_tx_hex"])) if r.get("trigger_tx_hex") else parse_tx(b"")
        win = parse_tx(bytes.fromhex(r["winner_tx_hex"])) if r.get("winner_tx_hex") else parse_tx(b"")
        static = [p for p in trig["pools"] if p.get("pk") and p["why"] == "static"]
        known = [p for p in static if p["pk"] in univ]
        route = None
        route_pk = None
        for p in known:
            kind = partner_kind(univ[p["pk"]], univ)
            if kind:
                route = kind
                route_pk = p["pk"]
                break
        win_static = [p for p in win["pools"] if p.get("pk")]
        win_known = [p for p in win_static if p["pk"] in univ]
        clip = None
        for p in win["pools"]:
            clip = sol_clip(int(p.get("amount") or 0))
            if clip is not None:
                break
        user_clip = None
        for p in trig["pools"]:
            user_clip = sol_clip(int(p.get("amount") or 0))
            if user_clip is not None:
                break
        scored.append({
            "cohort": r["cohort"],
            "sig": r["sig"],
            "trigger_sig": r.get("trigger_sig"),
            "slot": r.get("slot"),
            "profit": r.get("profit"),
            "who": (r.get("user") or "")[:6],
            "pair_hit": bool(r.get("pair_hit")),
            "trigger_recovered": bool(r.get("trigger_tx_hex")),
            "frame": trig["klass"],
            "frame_why": trig["why"],
            "dex_bytes": trig["dex_key_present"],
            "nkeys": trig["nkeys"],
            "swapix_static": bool(static),
            "pool_known": bool(known),
            "route": route,
            "route_pool": route_pk,
            "winner_pools": len(win_static),
            "winner_known": len(win_known),
            "winner_clip_sol": clip,
            "trigger_clip_sol": user_clip,
            "pool_why": (trig["pools"][0]["why"] if trig["pools"] else None),
        })
    return scored


def funnel(scored: list[dict], label: str) -> None:
    n = len(scored)
    def c(pred):
        xs = [r for r in scored if pred(r)]
        return len(xs), sum(r["profit"] or 0 for r in xs)

    steps = [
        ("KNOWN REAL HISTORICAL ARBS", lambda r: True),
        ("trigger recovered", lambda r: r["trigger_recovered"]),
        ("CORE010 FRAMED", lambda r: r["frame"] == "framed"),
        ("swapix static pool", lambda r: r["swapix_static"]),
        ("pool known", lambda r: r["pool_known"]),
        ("route compiled", lambda r: r["route"] in ("route0", "fam5")),
        ("route0 (hot path signs)", lambda r: r["route"] == "route0"),
        ("fam5 only", lambda r: r["route"] == "fam5"),
    ]
    print(f"\n{label}  n={n}  ${sum(r['profit'] or 0 for r in scored):.1f}")
    print(f"{'stage':<32} {'N':>5} {'$':>10}")
    for name, pred in steps:
        nn, usd = c(pred)
        print(f"{name:<32} {nn:5} {usd:10.1f}")
    print("state reconstructable           0  (no historical bin snapshot — quote not run)")
    print("positive at optimum             —")
    print("positive at 0.05 SOL            —")
    print("> current costs                 —")
    why = Counter(r["frame_why"] for r in scored if r["frame"] != "framed")
    print("frame drop reasons:", dict(why))
    pool_why = Counter(r["pool_why"] or "no_decoded_swap" for r in scored if r["frame"] == "framed" and not r["pool_known"])
    print("framed but pool unknown:", dict(pool_why))
    clips = [r["winner_clip_sol"] for r in scored if r["winner_clip_sol"] is not None]
    if clips:
        clips.sort()
        def pct(p):
            i = int(round((p / 100) * (len(clips) - 1)))
            return clips[i]
        over = sum(1 for x in clips if x > 0.05)
        print(
            f"winner first-hop amount looking like SOL: n={len(clips)} "
            f"p50={pct(50):.3f} p90={pct(90):.3f} max={clips[-1]:.3f} "
            f">0.05 SOL {over}/{len(clips)}"
        )
    else:
        print("winner first-hop SOL-like amount: none decoded")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    univ = load_univ(UNIV)
    rows = load_races()
    attach_hex(rows)
    rows = add_jackpot(rows)
    scored = score(rows, univ)
    late = [r for r in scored if r["cohort"] == "late121"]
    jack = [r for r in scored if r["profit"] >= 50 and r["cohort"] in ("late121", "jackpot_outside_121")]
    funnel(late, "LATE-BOOK DLMM→Pump")
    funnel(jack, "JACKPOT profit≥$50 DLMM→Pump (121 plus Mriya-class outside the late book)")
    out = ROOT / "arb-cap" / "regress" / "hist_funnel.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in scored), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
