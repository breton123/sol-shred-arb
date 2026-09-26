#!/bin/bash
# Impossible-profit dir=1 sim. Does not send the arb. Does not stop ONESHOT.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/exec_live002b.py
cp /tmp/exec_live002b.py /home/louis/arb-exec/scripts/exec_live002b.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
export SIM_DIR=1
cd /home/louis
python3 /home/louis/arb-exec/scripts/exec_live002b.py
python3 - <<'PY'
import json
from pathlib import Path
r = json.loads(Path("/home/louis/arb-cap/exec_live002b/report.json").read_text())
sim = r.get("simulate") or {}
print("DIR1_SIM err", sim.get("err"))
print("DIR1_SIM cu", sim.get("cu"))
print("DIR1_SIM tx", r.get("tx_len"), "margin", r.get("margin"))
print("--- last logs ---")
for line in (sim.get("logs") or [])[-20:]:
    print(line)
PY
