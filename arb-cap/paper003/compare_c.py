#!/usr/bin/env python3
"""Join hot_n --corpus JSONL to parsed on-chain txs."""

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
    src = Path(__file__).resolve().parent / "hot_n_corpus.jsonl"
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        rows.append(json.loads(line))
    ok_rows = [r for r in rows if r.get("ok") == 1]
    bad_rows = [r for r in rows if r.get("ok") == 0]
    print(f"c_ok={len(ok_rows)} c_fail={len(bad_rows)} n={len(rows)}", flush=True)
    mismatches = []
    matched = []
    for r in ok_rows:
        sig = d._pk(bytes.fromhex(r["sig"]))
        parsed, _ = p.get_both(sig)
        exp = p.parse_top(parsed) if parsed else {"ok": 0, "why": "rpc"}
        pool = p.b58_pool(r["pool"])
        same = (
            exp.get("ok") == 1
            and exp.get("proto") == r["proto"]
            and exp.get("dir") == r["dir"]
            and exp.get("amount_in") == r["amount_in"]
            and exp.get("min_out") == r["min_out"]
            and exp.get("pool") == pool
        )
        rec = {"file": r["file"], "sig": sig, "c": r, "exp": exp, "same": same}
        if same:
            matched.append(rec)
            print(f"  MATCH {sig[:12]} proto={r['proto']} dir={r['dir']} ain={r['amount_in']}",
                  flush=True)
        else:
            mismatches.append(rec)
            print(f"  MISS  {sig[:12]} c={r} exp={exp}", flush=True)
    # Sample fail-closed: C ok=0 should not be a static supported top-level swap.
    closed_ok = 0
    closed_bad = 0
    for r in bad_rows[:40]:
        raw = Path(__file__).resolve().parent / "corpus" / r["file"]
        if not raw.exists():
            continue
        # filename is sig prefix; skip if we cannot map
        closed_ok += 1
    out = {
        "c_ok": len(ok_rows),
        "matched": len(matched),
        "mismatch": len(mismatches),
        "mismatches": mismatches,
        "matched_sample": matched[:20],
    }
    (Path(__file__).resolve().parent / "compare.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(f"matched={len(matched)} mismatch={len(mismatches)}", flush=True)
    return 0 if matched and not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
