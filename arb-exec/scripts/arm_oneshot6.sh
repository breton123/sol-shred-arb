#!/bin/bash
# Arm ONESHOT#6: one mut_authoritative route0 send, then disarm. FUNDED=1.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/s007/oneshot_live.py /tmp/s007/run_oneshot.sh /tmp/s007/arm_oneshot6.sh
cp /tmp/s007/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/s007/run_oneshot.sh /home/louis/arb-exec/scripts/run_oneshot.sh
test -f /home/louis/captures/state007/READY || {
  echo "STATE007 not READY"
  exit 1
}
if test -e /home/louis/arb-cap/oneshot/ARMED; then
  echo "already ARMED"
  exit 1
fi
if ! test -S /home/louis/arb-cap/oneshot/swqos.sock; then
  bash /home/louis/arb-exec/scripts/start_racer.sh
fi
pgrep -c -f oneshot_live.py >/dev/null && {
  echo "oneshot already running"
  exit 75
}
export FUNDED=1
nohup bash /home/louis/arb-exec/scripts/run_oneshot.sh \
  >> /home/louis/arb-cap/oneshot/oneshot6.log 2>&1 < /dev/null &
echo "oneshot $!"
sleep 4
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_MISSING; tail -n 20 /home/louis/arb-cap/oneshot/oneshot6.log; fi
tail -n 12 /home/louis/arb-cap/oneshot/oneshot6.log
echo "paper=$(pgrep -c -f build/paper_orbit || true) s007=$(pgrep -c -f state007.py || true) racer=$(test -S /home/louis/arb-cap/oneshot/swqos.sock && echo up || echo down)"
