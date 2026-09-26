#!/usr/bin/env python3
import json
from pathlib import Path

r = json.loads(Path("/home/louis/arb-cap/exec_live002b/report.json").read_text())
sim = r.get("simulate") or {}
print("err", sim.get("err"))
print("cu", sim.get("cu"))
print("inner", sim.get("inner"))
print("LOGS")
for line in sim.get("logs") or []:
    print(line)
