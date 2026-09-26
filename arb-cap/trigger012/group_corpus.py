#!/usr/bin/env python3
"""Group executed CPI predecessors by outer program + disc.

Outcome per shape:
  1. amount always in outer bytes → deterministic decoder candidate
  2. amount never in outer bytes → UNPREDICTABLE_PREEXEC
  3. mixed → need more fields / S
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.jsonl"
OUT = HERE / "router_shapes.json"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not CORPUS.exists():
        print("no corpus yet")
        return 1
    rows = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    groups = defaultdict(list)
    for r in rows:
        venues = r.get("outer") or []
        pays = r.get("payloads") or []
        disc = pays[0]["disc"] if pays else ""
        dlen = pays[0]["data_len"] if pays else 0
        key = (venues[0] if venues else "?", disc, dlen)
        groups[key].append(r)
    shapes = []
    for (prog, disc, dlen), xs in sorted(groups.items(), key=lambda kv: -sum(r["usd"] for r in kv[1])):
        loci = defaultdict(lambda: {"n": 0, "usd": 0.0})
        for r in xs:
            loci[r.get("amount_locus") or "?"]["n"] += 1
            loci[r.get("amount_locus") or "?"]["usd"] += r.get("usd") or 0
        dominant = max(loci.items(), key=lambda kv: kv[1]["usd"])[0]
        verdict = "mixed"
        if dominant == "amount_in_outer_bytes" and len(loci) == 1:
            verdict = "deterministic_outer"
        elif dominant == "amount_absent_from_outer" and len(loci) == 1:
            verdict = "unpredictable_preexec"
        elif dominant == "amount_in_outer_bytes":
            verdict = "mostly_deterministic_outer"
        elif dominant == "amount_absent_from_outer":
            verdict = "mostly_unpredictable_preexec"
        shapes.append({
            "outer": prog,
            "disc": disc,
            "data_len": dlen,
            "n": len(xs),
            "usd": sum(r["usd"] for r in xs),
            "loci": dict(loci),
            "verdict": verdict,
            "example": xs[0].get("pred_sig"),
        })
    OUT.write_text(json.dumps(shapes, indent=2), encoding="utf-8")
    print(f"{'verdict':<32} {'n':>5} {'$':>10}  outer")
    for s in shapes[:25]:
        print(f"{s['verdict']:<32} {s['n']:5} {s['usd']:10.1f}  {s['outer'][:12]} disc={s['disc'][:16]} len={s['data_len']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
