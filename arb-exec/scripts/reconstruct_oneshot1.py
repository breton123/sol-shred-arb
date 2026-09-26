#!/usr/bin/env python3
"""Reconstruct ONESHOT #1 stale path. Observation only. No send."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/louis/arb-cap")
sys.path.insert(0, "/home/louis/arb-cap/paper004")
import live001 as live
import paper004 as p4
import record_dlmm as d

OURS = "3q6BM1m6EJkLVvXBbF8haSMnk6msVCY7U1awYoX96ufodD8byML3Nhct2k267cqsrxWafwTeFG2k1HWENbvDg2kr"
RESULT = Path("/home/louis/arb-cap/oneshot/RESULT.json")
OUT = Path("/home/louis/arb-cap/oneshot/STALE.json")
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
OUR_EXEC = "38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K"


def tx_sig(tx: dict) -> str:
    tr = tx.get("transaction") or {}
    sigs = tr.get("signatures") or []
    return sigs[0] if sigs else ""


def ix_pids_block(t: dict) -> set[str]:
    inner = t.get("transaction") or t
    if "message" in inner:
        return p4.ix_pids({"transaction": inner})
    return p4.ix_pids(t)


def keys_of(t: dict) -> list[str]:
    inner = t.get("transaction") or t
    if "message" in inner:
        return p4.tx_keys({"transaction": inner})
    return p4.tx_keys(t)


def touches(keys: list[str], pk: str) -> bool:
    return pk in keys


def classify_tx(t: dict, dlmm_pk: str, pump_pk: str) -> str:
    keys = keys_of(t)
    pids = ix_pids_block(t)
    err = (t.get("meta") or {}).get("err")
    hit_d = touches(keys, dlmm_pk)
    hit_p = touches(keys, pump_pk)
    both_prog = DLMM in pids and PUMP in pids
    our = OUR_EXEC in pids or OUR_EXEC in keys
    if our:
        return "ours"
    if both_prog or (hit_d and hit_p):
        return "competitor_arb"
    if hit_d or hit_p:
        return "pool_mutation"
    return "unrelated" if not err else "failed"


def fetch_block(slot: int) -> dict | None:
    try:
        return p4.rpc(
            "getBlock",
            [
                slot,
                {
                    "encoding": "json",
                    "transactionDetails": "full",
                    "rewards": False,
                    "maxSupportedTransactionVersion": 1,
                },
            ],
            pause=0.4,
        )
    except Exception as e:
        print(f"  getBlock {slot} {e}", flush=True)
        return None


def find_index(blk: dict | None, sig: str) -> int | None:
    if not blk:
        return None
    for i, t in enumerate(blk.get("transactions") or []):
        if tx_sig(t) == sig:
            return i
    return None


def main() -> int:
    live.load_dotenv()
    res = json.loads(RESULT.read_text(encoding="utf-8"))
    fire = res.get("fire") or {}
    opp = res.get("opp") or {}
    timing = opp.get("timing") or {}
    sig_hex = opp.get("sig_hex") or ""
    n_sig = p4.b58encode(bytes.fromhex(sig_hex)) if sig_hex else ""
    dlmm_pk = fire.get("dlmm") or ""
    pump_pk = fire.get("pump") or ""
    ours = fire.get("sig") or OURS

    print(f"N {n_sig}", flush=True)
    print(f"OURS {ours}", flush=True)

    n_tx = None
    n_err = None
    try:
        n_tx = p4.fetch_tx(n_sig)
    except Exception as e:
        n_err = str(e)
        print(f"  N fetch {e}", flush=True)
    our_tx = p4.fetch_tx(ours)
    n_slot = (n_tx or {}).get("slot")
    our_slot = (our_tx or {}).get("slot")
    n_bt = (n_tx or {}).get("blockTime")
    our_bt = (our_tx or {}).get("blockTime")
    n_landed = bool(n_tx) and (n_tx.get("meta") or {}).get("err") is None
    n_failed = bool(n_tx) and (n_tx.get("meta") or {}).get("err") is not None

    print(f"  N slot={n_slot} bt={n_bt} landed={n_landed} fail={n_failed}", flush=True)
    print(f"  OURS slot={our_slot} bt={our_bt} err={(our_tx or {}).get('meta', {}).get('err')}", flush=True)

    slots = []
    if n_slot:
        slots.append(int(n_slot))
    if our_slot and int(our_slot) not in slots:
        if n_slot and int(our_slot) > int(n_slot):
            for s in range(int(n_slot) + 1, int(our_slot)):
                if len(slots) < 8:
                    slots.append(s)
        slots.append(int(our_slot))

    intervening = []
    n_idx = None
    our_idx = None
    winner = None
    for slot in slots:
        blk = fetch_block(slot)
        if slot == n_slot:
            n_idx = find_index(blk, n_sig)
        if slot == our_slot:
            our_idx = find_index(blk, ours)
        txs = (blk or {}).get("transactions") or []
        print(f"  slot {slot} ntx={len(txs)} n_idx={n_idx if slot == n_slot else '-'} "
              f"our_idx={our_idx if slot == our_slot else '-'}", flush=True)
        for i, t in enumerate(txs):
            kind = classify_tx(t, dlmm_pk, pump_pk)
            if kind in ("unrelated", "failed") and tx_sig(t) not in (n_sig, ours):
                continue
            rec = {
                "slot": slot,
                "tx_index": i,
                "sig": tx_sig(t),
                "kind": kind,
                "err": (t.get("meta") or {}).get("err"),
                "fee": (t.get("meta") or {}).get("fee"),
                "searcher": (keys_of(t) or [""])[0],
            }
            if tx_sig(t) == n_sig:
                rec["kind"] = "N"
            if tx_sig(t) == ours:
                rec["kind"] = "OURS"
            intervening.append(rec)
            if rec["kind"] == "competitor_arb" and winner is None:
                after_n = (
                    (n_slot is None)
                    or slot > n_slot
                    or (slot == n_slot and (n_idx is None or i > n_idx))
                )
                before_us = (
                    slot < our_slot
                    or (slot == our_slot and (our_idx is None or i < our_idx))
                )
                if after_n and before_us:
                    winner = rec
            print(f"    [{i:03}] {rec['kind']:16} {rec['sig'][:16]} err={rec['err']}", flush=True)
        time.sleep(0.2)

    # Also scan pool sig lists in case getBlock missed (or N unseen).
    pool_scan = {}
    for label, pk in (("dlmm", dlmm_pk), ("pump", pump_pk)):
        try:
            sigs = p4.rpc("getSignaturesForAddress", [pk, {"limit": 30}], pause=0.25) or []
        except Exception as e:
            pool_scan[label] = {"error": str(e)}
            continue
        rows = []
        for ent in sigs:
            sl = int(ent.get("slot") or 0)
            if our_slot and sl > int(our_slot) + 2:
                continue
            if n_slot and sl < int(n_slot) - 2:
                continue
            rows.append({
                "sig": ent.get("signature"),
                "slot": sl,
                "err": ent.get("err"),
                "bt": ent.get("blockTime"),
            })
        pool_scan[label] = rows[:16]

    if not n_tx:
        letter = "C"
        why = "N never fetched / did not land"
    elif n_failed:
        letter = "C"
        why = "N landed with error — trigger did not execute"
    elif winner:
        letter = "A"
        why = "competitor arb between N and OURS"
    elif any(x["kind"] == "pool_mutation" for x in intervening if x["kind"] != "N"):
        letter = "B"
        why = "pool mutation between N and OURS, no atomic competitor arb seen"
    else:
        letter = "B"
        why = "no competitor arb in scanned blocks; quote still stale (setup delay and/or unseen mutation)"

    out = {
        "ours": ours,
        "n_sig": n_sig,
        "n_landed": n_landed,
        "n_failed": n_failed,
        "n_fetch_err": n_err,
        "n_slot": n_slot,
        "n_tx_index": n_idx,
        "n_block_time": n_bt,
        "ours_slot": our_slot,
        "ours_tx_index": our_idx,
        "ours_block_time": our_bt,
        "slot_delta": (int(our_slot) - int(n_slot)) if (n_slot and our_slot) else None,
        "block_time_delta_s": (int(our_bt) - int(n_bt)) if (n_bt and our_bt) else None,
        "timing_paper": {
            "T_N_actionable_ns": timing.get("actionable_ns"),
            "decision_ns": timing.get("decision_ns"),
            "signed_ready_ns": timing.get("signed_ready_ns"),
            "note": "actionable_ns is OrbitFlare shred rx (CLOCK_MONOTONIC_RAW). decision/signed_ready are paper_orbit rdtscp deltas, not ONESHOT sign/SWQOS.",
        },
        "timing_oneshot": {
            "T_decision": "oneshot printed gate then unlinked ARMED — no monotonic stamp",
            "T_signed": "after ATA + new ALT + 429s; no monotonic stamp",
            "T_SWQOS_return_send_ns": 6940,
            "T_SWQOS_return_wall_ms": fire.get("send_wall_ms"),
            "disarm_ts": res.get("ts"),
            "setup": "created ATA + new ALT J6jmHvne (~0.005 SOL) under Helius 429s before sign",
        },
        "winner": winner,
        "intervening": intervening,
        "pool_scan": pool_scan,
        "letter": letter,
        "why": why,
        "opp": {
            "pool": opp.get("pool"),
            "arb": opp.get("arb"),
            "n": opp.get("n"),
            "auth_slot": opp.get("auth_slot"),
        },
        "fire": {
            "dlmm": dlmm_pk,
            "pump": pump_pk,
            "direction": fire.get("direction"),
            "send": fire.get("send_lamports"),
            "est_gp": fire.get("est_gp"),
            "alt": fire.get("alt"),
            "status_err": (fire.get("status") or {}).get("err"),
        },
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "letter": letter,
        "why": why,
        "n_slot": n_slot,
        "n_tx_index": n_idx,
        "ours_slot": our_slot,
        "ours_tx_index": our_idx,
        "slot_delta": out["slot_delta"],
        "block_time_delta_s": out["block_time_delta_s"],
        "winner": (winner or {}).get("sig"),
        "T_N_actionable_ns": timing.get("actionable_ns"),
        "decision_ns": timing.get("decision_ns"),
        "signed_ready_ns": timing.get("signed_ready_ns"),
        "swqos_send_ns": 6940,
        "swqos_wall_ms": fire.get("send_wall_ms"),
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
