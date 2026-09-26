#!/usr/bin/env python3
"""Off-path landing + same-slot sibling scan for FLOWRA1 N events.

RPC observation is NOT leader sequencing latency.
Does not quote S_today. Does not call hot_decide.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
VENUES = {
    DLMM,
    PUMP,
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C",
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
}


def rpc_url() -> str:
    u = (os.environ.get("HELIUS_RPC_URL") or os.environ.get("RPC_URL") or "").strip()
    if u:
        return u
    k = (os.environ.get("HELIUS_API_KEY") or "").strip()
    if not k:
        raise SystemExit("set RPC_URL or HELIUS_RPC_URL or HELIUS_API_KEY")
    return f"https://mainnet.helius-rpc.com/?api-key={k}"


def rpc(method: str, params, pause=0.12):
    url = rpc_url()
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for _ in range(8):
        time.sleep(pause)
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                obj = json.loads(r.read().decode())
            if "error" in obj:
                msg = str(obj["error"])
                if "429" in msg or "rate" in msg.lower():
                    time.sleep(1.5)
                    last = msg
                    continue
                raise RuntimeError(msg)
            return obj.get("result")
        except urllib.error.HTTPError as e:
            last = str(e)
            if e.code == 429:
                time.sleep(1.5)
                continue
            raise
        except Exception as e:
            last = str(e)
            time.sleep(0.5)
    raise RuntimeError(last or "rpc fail")


def load_n(path: Path) -> list[dict]:
    rows = []
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def statuses(sigs: list[str]) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    for i in range(0, len(sigs), 100):
        chunk = sigs[i : i + 100]
        res = rpc("getSignatureStatuses", [chunk, {"searchTransactionHistory": True}])
        vals = (res or {}).get("value") or []
        for sig, ent in zip(chunk, vals):
            out[sig] = ent
        print(f"  statuses {min(i + 100, len(sigs))}/{len(sigs)}", flush=True)
    return out


def tx_keys(tx: dict) -> list[str]:
    msg = ((tx.get("transaction") or {}).get("message") or {})
    keys = list(msg.get("accountKeys") or [])
    out = []
    for k in keys:
        if isinstance(k, dict):
            out.append(k.get("pubkey") or "")
        else:
            out.append(str(k))
    return out


def ix_pids(tx: dict) -> set[str]:
    keys = tx_keys(tx)
    pids: set[str] = set()
    msg = ((tx.get("transaction") or {}).get("message") or {})
    for ix in msg.get("instructions") or []:
        pid = ix.get("programId")
        if pid is None:
            i = ix.get("programIdIndex")
            if i is not None and i < len(keys):
                pid = keys[i]
        if pid:
            pids.add(pid)
    for g in (tx.get("meta") or {}).get("innerInstructions") or []:
        for ix in g.get("instructions") or []:
            pid = ix.get("programId")
            if pid is None:
                i = ix.get("programIdIndex")
                if i is not None and i < len(keys):
                    pid = keys[i]
            if pid:
                pids.add(pid)
    return pids


def main() -> None:
    npath = Path(sys.argv[1] if len(sys.argv) > 1 else "n.jsonl")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else npath.parent / "landing.json")
    sibling_cap = int(os.environ.get("FLOWRA_SIBLING_SLOTS", "24"))
    rows = load_n(npath)
    trig = [r for r in rows if r.get("trigger_ok")]
    known = [r for r in trig if r.get("known_pool")]
    print(f"n.jsonl={len(rows)} trigger={len(trig)} known_trig={len(known)}", flush=True)
    if not trig:
        out.write_text(json.dumps({"sampled": 0, "note": "no trigger rows"}, indent=2) + "\n")
        return

    st = statuses([r["sig"] for r in trig])
    landed = []
    failed = 0
    unseen = 0
    for r in trig:
        ent = st.get(r["sig"])
        if not ent:
            unseen += 1
            continue
        if ent.get("err") is not None:
            failed += 1
            continue
        if ent.get("slot") or ent.get("confirmationStatus"):
            landed.append({**r, "slot": ent.get("slot"), "conf": ent.get("confirmationStatus")})

    known_landed = [r for r in landed if r.get("known_pool")]
    same_tx_arb = 0
    fetched = 0
    slots = []
    for r in known_landed[:400]:
        try:
            tx = rpc(
                "getTransaction",
                [r["sig"], {"encoding": "json", "maxSupportedTransactionVersion": 1}],
            )
        except Exception as e:
            print(f"  tx fail {r['sig'][:8]} {e}", flush=True)
            continue
        fetched += 1
        if not tx:
            continue
        pids = ix_pids(tx)
        if DLMM in pids and PUMP in pids:
            same_tx_arb += 1
        slots.append(int(tx.get("slot") or r.get("slot") or 0))

    sibling_hits = 0
    sibling_slots = 0
    unique_slots = []
    seen_slot = set()
    for s in slots:
        if s and s not in seen_slot:
            seen_slot.add(s)
            unique_slots.append(s)
    for slot in unique_slots[:sibling_cap]:
        try:
            blk = rpc(
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
                pause=0.25,
            )
        except Exception as e:
            print(f"  block fail {slot} {e}", flush=True)
            continue
        sibling_slots += 1
        txs = (blk or {}).get("transactions") or []
        others = 0
        for t in txs:
            meta = t.get("meta") or {}
            if meta.get("err"):
                continue
            inner = t.get("transaction") or t
            pids = ix_pids(inner if "message" in inner else t)
            # json block shape: transaction.message
            if not pids:
                pids = ix_pids(t)
            if DLMM in pids and PUMP in pids:
                others += 1
        if others >= 2:
            sibling_hits += 1
        print(f"  slot {slot} dlmm+pump_txs={others}", flush=True)

    report = {
        "trigger_sampled": len(trig),
        "known_trigger": len(known),
        "landed": len(landed),
        "known_landed": len(known_landed),
        "failed": failed,
        "expired_or_unseen": unseen,
        "landed_rate_trigger": (len(landed) / len(trig)) if trig else 0,
        "getTransaction_known_landed": fetched,
        "same_tx_dlmm_and_pump": same_tx_arb,
        "sibling_slots_scanned": sibling_slots,
        "slots_with_ge2_dlmm_pump": sibling_hits,
        "note": (
            "RPC landing is not leader latency. "
            "same_tx_dlmm_and_pump = the pending tx itself contained both venues. "
            "slots_with_ge2_dlmm_pump = another DLMM+Pump tx in the same landed slot "
            "(possible backrun / searcher). Not proof we would have won. "
            "No S_today quotes. No hot_decide."
        ),
    }
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
