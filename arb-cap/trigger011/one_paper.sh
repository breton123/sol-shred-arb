#!/usr/bin/env bash
set -eu
pids=$(pgrep -f '/home/louis/arb-feed/.*/paper_orbit' || true)
if [ -n "$pids" ]; then
  kill $pids 2>/dev/null || true
fi
sleep 1
pids=$(pgrep -f '/home/louis/arb-feed/.*/paper_orbit' || true)
if [ -n "$pids" ]; then
  kill -9 $pids 2>/dev/null || true
fi
sleep 1
export PAPER_SECONDS=43200
export PAPER_SYNC="${HOME}/captures/paper_orbit/sync_state006.bin"
nohup /home/louis/arb-feed/scripts/paper_orbit.sh \
  >/home/louis/captures/paper_orbit/paper_trig011.log 2>&1 &
sleep 2
pgrep -a paper_orbit || echo paper_missing
strings /home/louis/captures/paper_orbit/paper_trig011.log | grep TRIGGER-011 | tail -n 3
echo oneshot=$(ls /home/louis/arb-cap/oneshot/DISARMED)
