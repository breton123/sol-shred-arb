#!/usr/bin/env python3
"""Compare decode_feed shred decodes to parsed on-chain txs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prove_decode as p  # noqa: E402
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

live.load_dotenv()


def main() -> int:
    src = Path(__file__).resolve().parent / "decode_feed.jsonl"
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.startswith("{")]
    need = 80
    matched = []
    mismatch = []
    skipped = []
    print(f"feed unique={len(rows)} checking {need}", flush=True)
    for r in rows:
        if len(matched) + len(mismatch) >= need:
            break
        sig = d._pk(bytes.fromhex(r["sig"]))
        try:
            parsed = d.rpc("getTransaction", [
                sig, {"encoding": "json", "maxSupportedTransactionVersion": 1},
            ])
        except Exception as e:
            skipped.append(sig)
            print(f"  skip {sig[:12]} {type(e).__name__}", flush=True)
            continue
        exp = p.parse_top(parsed) if parsed else {"ok": 0, "why": "missing"}
        pool = p.b58_pool(r["pool"])
        same = (
            exp.get("ok") == 1
            and exp.get("proto") == r["proto"]
            and exp.get("dir") == r["dir"]
            and exp.get("amount_in") == r["amount_in"]
            and exp.get("min_out") == r["min_out"]
            and exp.get("pool") == pool
        )
        if same:
            matched.append({"sig": sig, **r})
            print(f"  MATCH {sig[:12]} proto={r['proto']} dir={r['dir']} ain={r['amount_in']}",
                  flush=True)
        else:
            mismatch.append({"sig": sig, "c": r, "exp": exp})
            print(f"  MISS  {sig[:12]} why={exp.get('why')} c_ain={r['amount_in']}",
                  flush=True)
    out = {
        "checked": len(matched) + len(mismatch),
        "matched": len(matched),
        "mismatch": len(mismatch),
        "skipped": len(skipped),
        "mismatches": mismatch[:15],
    }
    Path(__file__).resolve().parent.joinpath("compare_feed.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(f"matched={len(matched)} mismatch={len(mismatch)} skip={len(skipped)}", flush=True)
    return 0 if matched and not mismatch else 1


if __name__ == "__main__":
    raise SystemExit(main())
