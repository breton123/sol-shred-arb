#!/usr/bin/env python3
"""Locate the $0.61 and $352.96 phantoms in the PAPER-LIVE-001 journal."""

from __future__ import annotations

import json
import struct
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOL_USD = 115.0
JRN = ROOT / "paper_live001" / "journal.bin"
UNIV = ROOT / "live002" / "liveuniv.json"
FAM = {0: "DLMM+Pump", 1: "CLMM+DLMM", 2: "CPMM+DLMM", 3: "DLMM+DAMM",
       4: "ORCA+DLMM", 255: "OTHER"}


def lamports_usd(x: int) -> float:
    return x * SOL_USD / 1e9


def load_journal(path: Path) -> list[dict]:
    raw = path.read_bytes()
    recs = []
    off = 4
    while off + 64 <= len(raw):
        t = struct.unpack_from("<QQQQQIII BBBBBBBB 4x", raw, off)
        off += 64
        recs.append({
            "rx_ns": t[0], "act_ns": t[1], "sign_ns": t[2],
            "amount_in": t[3], "gross": t[4], "slot": t[5],
            "pool_idx": t[6], "route_id": t[7], "family": t[8],
            "n_hop": t[9], "proto": (t[10], t[11], t[12]),
            "searchable": t[13], "signed_ready": t[14], "reason": t[15],
        })
    return recs


def main() -> int:
    recs = load_journal(JRN)
    meta = json.loads(UNIV.read_text(encoding="utf-8"))
    pools = meta["pools"]
    print(f"liveuniv slot={meta['slot']} n={meta['n']}")
    print(f"capture slots in journal: {min(r['slot'] for r in recs)} .. {max(r['slot'] for r in recs)}")
    print(f"slot delta live-capture ~ {meta['slot'] - min(r['slot'] for r in recs)}")

    # $0.61 cluster
    c61 = [r for r in recs if 0.60 <= lamports_usd(r["gross"]) <= 0.62]
    print(f"\n$0.61-ish n={len(c61)}")
    print("  pool_idx", Counter(r["pool_idx"] for r in c61).most_common(8))
    print("  route_id", Counter(r["route_id"] for r in c61).most_common(8))
    print("  family", Counter(r["family"] for r in c61).most_common())
    print("  amount_in", Counter(r["amount_in"] for r in c61).most_common(5))
    print("  gross", Counter(r["gross"] for r in c61).most_common(5))
    if c61:
        r = c61[0]
        p = pools[r["pool_idx"]] if r["pool_idx"] < len(pools) else {}
        print(f"  sample pool {r['pool_idx']} {p.get('kind')} {p.get('pubkey','')[:12]} "
              f"ain={r['amount_in']} gp={r['gross']} usd={lamports_usd(r['gross']):.4f}")

    # $352.96 cluster
    c352 = [r for r in recs if 352.0 <= lamports_usd(r["gross"]) <= 354.0]
    print(f"\n$352-ish n={len(c352)}")
    print("  pool_idx", Counter(r["pool_idx"] for r in c352).most_common(8))
    print("  route_id", Counter(r["route_id"] for r in c352).most_common(8))
    print("  family", Counter(r["family"] for r in c352).most_common())
    print("  hops", Counter(r["n_hop"] for r in c352).most_common())
    print("  proto", Counter(r["proto"] for r in c352).most_common(5))
    print("  amount_in", Counter(r["amount_in"] for r in c352).most_common(5))
    print("  gross", Counter(r["gross"] for r in c352).most_common(5))
    print("  first 10:")
    for r in c352[:10]:
        p = pools[r["pool_idx"]] if r["pool_idx"] < len(pools) else {}
        print(f"    slot={r['slot']} pool={r['pool_idx']}:{p.get('kind')} "
              f"{str(p.get('pubkey',''))[:8]} rid={r['route_id']} "
              f"proto={r['proto']} ain={r['amount_in']} gp={r['gross']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
