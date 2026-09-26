#!/usr/bin/env python3
import json
from pathlib import Path

OUT = Path("/home/louis/arb-cap/oneshot")
for name in ("ARMED", "DISARMED", "RESULT.json", "signed.tx"):
    p = OUT / name
    print(f"{name} exists={p.exists()} size={p.stat().st_size if p.exists() else 0}")
if (OUT / "RESULT.json").exists():
    print((OUT / "RESULT.json").read_text()[:2000])
if (OUT / "DISARMED").exists():
    print("DISARMED", (OUT / "DISARMED").read_text()[:800])
tx = OUT / "signed.tx"
if tx.exists() and tx.stat().st_size >= 65:
    raw = tx.read_bytes()
    print(f"signed.tx len={len(raw)}")
