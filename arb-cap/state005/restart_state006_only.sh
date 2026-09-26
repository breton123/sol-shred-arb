#!/bin/bash
# Restart AUTH refresh only. Paper and ONESHOT#6 stay.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/expand6/state006.py /tmp/expand6/agg_searchable.py
cp /tmp/expand6/state006.py /home/louis/arb-cap/state005/state006.py
cp /tmp/expand6/agg_searchable.py /home/louis/arb-cap/state005/agg_searchable.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
python3 - <<'PY'
import os, signal
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"state005/state006.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 0.6
nohup python3 /home/louis/arb-cap/state005/state006.py \
  >> /home/louis/captures/paper_orbit/state006.log 2>&1 < /dev/null &
echo "state006 $!"
sleep 4
echo "=== state ==="
tail -n 8 /home/louis/captures/paper_orbit/state006.log
echo "=== oneshot ==="
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_MISSING
pgrep -c -f state005/state006.py || true
pgrep -c -f oneshot_live.py || true
pgrep -c -f build/paper_orbit || true
python3 /home/louis/arb-cap/state005/agg_searchable.py
