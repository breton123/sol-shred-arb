#!/usr/bin/env python3
"""Pack 171k trial arb signatures as raw 64-byte keys for paper_live001."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALPH = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58_n(s: str, n: int) -> bytes:
    num = 0
    for c in s:
        num = num * 58 + ALPH.index(c)
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    h = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    raw = b"\x00" * pad + h
    if len(raw) < n:
        raw = raw.rjust(n, b"\x00")
    return raw[-n:]


def main() -> int:
    src = ROOT / "all_arbs_trial.jsonl"
    out = ROOT / "paper_live001" / "winner_sigs.bin"
    n = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as f:
        for line in src.open(encoding="utf-8"):
            r = json.loads(line)
            sig = r.get("signature")
            if not sig:
                continue
            raw = b58_n(sig, 64)
            if len(raw) != 64:
                continue
            f.write(raw)
            n += 1
    print(f"wrote {out} n={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
