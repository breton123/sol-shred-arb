#!/bin/bash
# Kill the funded oneshot. Do not restart it.
set -euo pipefail
python3 - <<'PY'
import os, signal
from pathlib import Path
armed = Path("/home/louis/arb-cap/oneshot/ARMED")
dis = Path("/home/louis/arb-cap/oneshot/DISARMED")
if armed.exists():
    armed.unlink()
dis.write_text('{"why":"closure_hops","funded":0,"note":"oneshot6 stopped; hops plane next"}\n', encoding="utf-8")
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"oneshot_live.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped_oneshot", pid)
print("ONESHOT6_OFF")
PY
if [[ -f /home/louis/arb-exec/scripts/run_oneshot.sh ]]; then
  sed -i 's/export FUNDED=1/export FUNDED=0/' /home/louis/arb-exec/scripts/run_oneshot.sh || true
fi
pgrep -af oneshot_live.py || echo oneshot_absent
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_ABSENT
