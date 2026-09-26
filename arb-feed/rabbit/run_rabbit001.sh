#!/bin/bash
# Observe-only RabbitStream. Does not touch ONESHOT / STATE-007 / paper.
set -euo pipefail
mkdir -p /home/louis/captures/rabbit /home/louis/arb-feed/rabbit
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/s007/rabbit001.py /tmp/s007/agg_rabbit.py /tmp/s007/run_rabbit001.sh
cp /tmp/s007/rabbit001.py /home/louis/arb-feed/rabbit/rabbit001.py
cp /tmp/s007/agg_rabbit.py /home/louis/arb-feed/rabbit/agg_rabbit.py
# Do not kill oneshot, paper, state007, racer.
python3 - <<'PY'
import os, signal
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"arb-feed/rabbit/rabbit001.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped_old_rabbit", pid)
PY
sleep 0.4
set -a
. /home/louis/.arb-smoke.env
. /home/louis/.arb-state007.env
set +a
export RABBIT_GRPC_URL="${RABBIT_GRPC_URL:-rabbitstream.fra.shyft.to:443}"
nohup python3 /home/louis/arb-feed/rabbit/rabbit001.py \
  >> /home/louis/captures/rabbit/rabbit001.log 2>&1 < /dev/null &
echo "rabbit $!"
sleep 6
echo "=== rabbit ==="
tail -n 12 /home/louis/captures/rabbit/rabbit001.log
echo "=== funded untouched ==="
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_ABSENT; fi
pgrep -c -f oneshot_live.py || true
pgrep -c -f state007.py || true
pgrep -c -f build/paper_orbit || true
