#!/usr/bin/env bash
set -euo pipefail
for p in $(pgrep -f '/home/louis/arb-feed/build/paper_orbit' || true); do
  kill "$p" 2>/dev/null || true
done
sleep 1
for p in $(pgrep -f '/home/louis/arb-feed/build/paper_orbit' || true); do
  kill -9 "$p" 2>/dev/null || true
done
export PAPER_SECONDS=43200
export PAPER_SYNC="${HOME}/captures/paper_orbit/sync_state006.bin"
nohup /home/louis/arb-feed/scripts/paper_orbit.sh \
  >/home/louis/captures/paper_orbit/paper_hops.log 2>&1 &
sleep 2
pgrep -a -f '/home/louis/arb-feed/build/paper_orbit' || true
grep -E 'TRIGGER-011|watch=' /home/louis/captures/paper_orbit/paper_hops.log | tail -n 8 || true
ls /home/louis/arb-cap/oneshot/DISARMED 2>/dev/null || true
pgrep -a -f oneshot_live.py || true
pgrep -a -f state007.py || true
