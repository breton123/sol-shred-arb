#!/bin/bash
# STATE-007: FUNDED stays 0. Stop oneshot. Do not send.
set -euo pipefail
python3 - <<'PY'
import os, signal
from pathlib import Path
armed = Path("/home/louis/arb-cap/oneshot/ARMED")
dis = Path("/home/louis/arb-cap/oneshot/DISARMED")
if armed.exists():
    armed.unlink()
dis.write_text('{"why":"state007_funded0","funded":0}\n', encoding="utf-8")
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
print("FUNDED=0  ARMED removed")
PY
# Keep the launcher from re-arming funded.
if [[ -f /home/louis/arb-exec/scripts/run_oneshot.sh ]]; then
  sed -i 's/export FUNDED=1/export FUNDED=0/' /home/louis/arb-exec/scripts/run_oneshot.sh || true
fi
echo "=== oneshot ==="
pgrep -af oneshot_live.py || echo "oneshot_absent"
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_ABSENT
echo "paper=$(pgrep -c -f build/paper_orbit || true) state006=$(pgrep -c -f state005/state006.py || true)"
