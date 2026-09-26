#!/bin/bash
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/home/louis/arb-cap/exec_live002b/report.json")
r = json.loads(p.read_text())
sim = r.get("simulate") or {}
print("err", sim.get("err"))
print("cu", sim.get("cu"))
print("inner", sim.get("inner"))
print("missing", r.get("missing"))
print("LOGS")
for line in sim.get("logs") or []:
    print(line)
PY
