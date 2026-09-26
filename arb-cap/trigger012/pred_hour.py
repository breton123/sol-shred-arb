#!/usr/bin/env python3
"""Causal predecessor for every live-hour DLMM/Pump winner.

Nearest preceding non-vote, non-err, non-arb tx whose resolved
program set includes DLMM or Pump (outer or inner CPI).
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARBS = HERE / "hour_arbs.jsonl"
SLIM = HERE / "slim"
OUT = HERE / "predecessors.jsonl"
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


def load_slim(slot: int) -> dict | None:
    p = SLIM / f"{slot}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def predecessor(block: dict, winner: str, arb_sigs: set[str]) -> dict | None:
    txs = block.get("txs") or []
    idx = None
    for t in txs:
        if t.get("sig") == winner:
            idx = int(t["i"])
            break
    if idx is None:
        return {"why": "winner_not_in_block"}
    looked = 0
    for t in reversed(txs[:idx]):
        if t.get("vote") or t.get("err"):
            continue
        looked += 1
        sig = t.get("sig")
        if sig in arb_sigs:
            continue
        pids = t.get("pids") or []
        if t.get("dex") or DLMM in pids or PUMP in pids:
            return {
                "sig": sig,
                "i": int(t["i"]),
                "dist": idx - int(t["i"]),
                "looked": looked,
                "why": "ok",
            }
        if looked >= 120:
            break
    return {"why": "no_dex_before", "looked": looked, "winner_i": idx}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arbs = []
    for line in ARBS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            arbs.append(json.loads(line))
    arb_sigs = {r["sig"] for r in arbs}
    rows = []
    for r in arbs:
        slot = r.get("slot")
        block = load_slim(int(slot)) if slot else None
        pred = predecessor(block, r["sig"], arb_sigs) if block and not block.get("error") else None
        if pred is None:
            pred = {"why": "no_slim" if not block else "slim_error"}
        rows.append({
            "winner": r["sig"],
            "slot": slot,
            "usd": r.get("usd") or 0,
            "pred_sig": pred.get("sig"),
            "dist": pred.get("dist"),
            "pred_why": pred.get("why"),
            "looked": pred.get("looked"),
        })
    OUT.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
    n = len(rows)
    usd = sum(r["usd"] for r in rows)
    found = [r for r in rows if r.get("pred_sig")]
    print(f"arbs={n} ${usd:.1f}")
    print(f"pred found {len(found)} ${sum(r['usd'] for r in found):.1f}")
    from collections import Counter
    print("why", dict(Counter(r["pred_why"] for r in rows)))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
