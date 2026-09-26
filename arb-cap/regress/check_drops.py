#!/usr/bin/env python3
"""Sanity-check frame drop reasons on a few historical triggers."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import hist_funnel as h

rows = []
for line in h.RACES.read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        if r.get("supported") and r.get("route") == "Meteora DLMM → Pump Swap":
            r["cohort"] = "late121"
            rows.append(r)
h.attach_hex(rows)
univ = h.load_univ(h.UNIV)
scored = {r["sig"]: r for r in h.score(rows, univ)}

nsig_vals = []
no_dex_lens = []
static_missing = []
for r in rows:
    raw = bytes.fromhex(r["trigger_tx_hex"]) if r.get("trigger_tx_hex") else b""
    parsed = h.parse_tx(raw)
    s = scored[r["sig"]]
    if parsed["why"] == "nsig_range":
        nsig, _ = h.cu16(raw, 0)
        nsig_vals.append((nsig, len(raw), r["profit"], r["trigger_sig"][:12]))
    if parsed["why"] == "no_dex_bytes":
        no_dex_lens.append(len(raw))
    if parsed["klass"] == "framed" and not s["pool_known"]:
        pks = [p.get("pk") for p in parsed["pools"] if p.get("pk")]
        if pks:
            static_missing.append((r["profit"], pks[0], parsed["pools"][0]["why"]))

print("nsig_range samples (nsig, nbytes, profit):")
for row in sorted(nsig_vals, key=lambda x: -x[2])[:8]:
    print(" ", row)
print("nsig counter", Counter(n for n, *_ in nsig_vals))
print("no_dex nbytes", "n", len(no_dex_lens), "min", min(no_dex_lens) if no_dex_lens else None, "max", max(no_dex_lens) if no_dex_lens else None)
print("framed static pools NOT in universe, top profit:")
for row in sorted(static_missing, key=lambda x: -x[0])[:8]:
    print(f"  ${row[0]:.2f}  {row[1]}  {row[2]}")
print("unique missing static pools", len({p for _, p, _ in static_missing}))
