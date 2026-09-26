#!/usr/bin/env python3
"""Validate a Codex placement/cancel/swap corpus when it exists.

Expected files (any subset):
  corpus/placements.jsonl   — 16/16 known placement deltas
  corpus/cancellations.jsonl
  corpus/swaps.jsonl        — TX_EXACT quotes/fills across order-inventory bins

Each placement/cancel line:
  {id, before: Bin, after: Bin, expect_delta?: {...}, mm_unchanged?: bool}

Each swap line:
  {id, bin, swap_for_y, support_limit_order?,
   amount_out_kernel?, amount_out_official?,
   committed?: {amount_x, amount_y, open, proc_rem}}

STATE-010 soak is not started or restarted from here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from inventory import (
    available_output,
    kernel_available_output,
    mm_unchanged,
    placement_delta,
)

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"


def _load(name: str) -> list[dict]:
    p = CORPUS / name
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _check_delta(rows: list[dict], label: str) -> tuple[int, int]:
    ok = 0
    n = 0
    for row in rows:
        n += 1
        d = placement_delta(row["before"], row["after"])
        exp = row.get("expect_delta")
        if exp:
            fail = any(int(d.get(k, 0)) != int(v) for k, v in exp.items())
            if fail:
                print(f"FAIL {label} {row.get('id')} delta={d} expect={exp}")
                continue
        if "mm_unchanged" in row and bool(row["mm_unchanged"]) != mm_unchanged(d):
            print(f"FAIL {label} {row.get('id')} mm_unchanged")
            continue
        ok += 1
    return ok, n


def _check_swaps(rows: list[dict]) -> tuple[int, int]:
    ok = 0
    n = 0
    for row in rows:
        n += 1
        b = row["bin"]
        sfy = bool(row["swap_for_y"])
        sup = bool(row.get("support_limit_order", True))
        off = available_output(b, sfy, support_limit_order=sup)
        ker = kernel_available_output(b, sfy)
        if "amount_out_official" in row and int(row["amount_out_official"]) != off:
            print(f"FAIL swap {row.get('id')} official {off} != {row['amount_out_official']}")
            continue
        if "amount_out_kernel" in row and int(row["amount_out_kernel"]) != ker:
            print(f"FAIL swap {row.get('id')} kernel {ker} != {row['amount_out_kernel']}")
            continue
        if row.get("expect_kernel_underfill") and not (ker < off):
            print(f"FAIL swap {row.get('id')} expected kernel underfill ker={ker} off={off}")
            continue
        ok += 1
    return ok, n


def main() -> int:
    pl = _load("placements.jsonl")
    ca = _load("cancellations.jsonl")
    sw = _load("swaps.jsonl")
    pok, pn = _check_delta(pl, "place")
    cok, cn = _check_delta(ca, "cancel")
    sok, sn = _check_swaps(sw)
    print(
        json.dumps(
            {
                "placements": f"{pok}/{pn}" if pn else "MISSING",
                "cancellations": f"{cok}/{cn}" if cn else "MISSING",
                "swaps": f"{sok}/{sn}" if sn else "MISSING",
                "note": "16/16 + 43/43 Codex files not in-tree; drop jsonl under corpus/",
            },
            indent=2,
        )
    )
    if not pn and not cn and not sn:
        return 2
    return 0 if pok == pn and cok == cn and sok == sn else 1


if __name__ == "__main__":
    sys.exit(main())
