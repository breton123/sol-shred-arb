#!/usr/bin/env python3
"""Faster: JSON first, keep only supported top-level swaps, then raw bytes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prove_decode as p  # noqa: E402
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

live.load_dotenv()
OUT = Path(__file__).resolve().parent
CORPUS = OUT / "corpus"
NEED = 80


def main() -> int:
    CORPUS.mkdir(parents=True, exist_ok=True)
    have = {x.stem for x in CORPUS.glob("*.bin")}
    sigs = p.collect_sigs(400)
    # more from arbs
    arbs = OUT.parent / "all_arbs_trial.jsonl"
    extra = []
    if arbs.exists():
        for line in arbs.open(encoding="utf-8"):
            r = json.loads(line)
            s = r.get("signature")
            if s:
                extra.append(s)
            if len(extra) >= 4000:
                break
    sigs = list(dict.fromkeys(sigs + extra))
    supported = []
    print(f"scan {len(sigs)} have_corpus={len(have)}", flush=True)
    for sig in sigs:
        if len(supported) >= NEED:
            break
        if sig[:16] in have:
            continue
        try:
            parsed = d.rpc("getTransaction", [
                sig, {"encoding": "json", "maxSupportedTransactionVersion": 1},
            ])
        except Exception as e:
            print(f"  skip {sig[:8]} {type(e).__name__}", flush=True)
            continue
        exp = p.parse_top(parsed) if parsed else {"ok": 0}
        if not exp.get("ok"):
            continue
        try:
            r = d.rpc("getTransaction", [
                sig, {"encoding": "base64", "maxSupportedTransactionVersion": 1},
            ])
            tx = (r or {}).get("transaction")
            raw = None
            if isinstance(tx, list) and tx:
                import base64
                raw = base64.b64decode(tx[0])
        except Exception:
            raw = None
        if not raw:
            continue
        path = CORPUS / f"{sig[:16]}.bin"
        path.write_bytes(raw)
        exp["sig"] = sig
        supported.append(exp)
        print(f"  +{len(supported)} {sig[:12]} proto={exp['proto']} ain={exp['amount_in']}",
              flush=True)
    (OUT / "supported.json").write_text(json.dumps(supported, indent=2), encoding="utf-8")
    print(f"wrote {len(supported)} supported", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
