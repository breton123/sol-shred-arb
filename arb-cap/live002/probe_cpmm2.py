#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live001 as live  # noqa: E402
import live002 as l  # noqa: E402
import record_dlmm as d  # noqa: E402

live.load_dotenv()
pk = "B4VFURUHdK1sC8nm8ePvd1MYBxS1DR8yhscwSLE1sZ7"
acc = d.get_multiple([pk])[0]
data = acc["data"]
sol = d.b58decode(l.SOL)
print("len", len(data), "sol", l.find_mint(data, sol))
for off in range(0, min(len(data) - 31, 400), 4):
    s = d._pk(data[off : off + 32])
    if s.startswith("So11111") or off in (8, 40, 72, 104, 136, 168, 200, 232):
        print(f"  {off:4} {s}")
