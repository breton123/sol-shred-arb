#!/bin/bash
# Install x-token env and restart STATE-007 only. FUNDED stays 0.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/config.py /tmp/s007/reauth.sh
cp /tmp/s007/config.py /home/louis/arb-state/shyft/config.py
if [[ -f /tmp/s007/shyft.env ]]; then
  chmod 600 /tmp/s007/shyft.env
  cp /tmp/s007/shyft.env /home/louis/.arb-state007.env
  chmod 600 /home/louis/.arb-state007.env
  rm -f /tmp/s007/shyft.env
fi
python3 - <<'PY'
import os, signal
from pathlib import Path
p = Path.home() / ".arb-state007.env"
txt = p.read_text(encoding="utf-8") if p.exists() else ""
print("env_bytes", p.stat().st_size if p.exists() else 0)
print("has_SHYFT_TOKEN", "SHYFT_TOKEN=" in txt)
print("has_url", "SHYFT_GRPC_URL=" in txt)
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"arb-state/shyft/state007.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 0.6
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
# shellcheck disable=SC1091
. /home/louis/.arb-state007.env
set +a
nohup python3 /home/louis/arb-state/shyft/state007.py \
  >> /home/louis/captures/state007/state007.log 2>&1 < /dev/null &
echo "state007 $!"
sleep 8
echo "=== log ==="
tail -n 16 /home/louis/captures/state007/state007.log
echo "=== funded ==="
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_ABSENT; fi
grep FUNDED /home/louis/arb-exec/scripts/run_oneshot.sh
