#!/usr/bin/env bash
set -euo pipefail
export PAPER_SECONDS=43200
export PAPER_SYNC="${HOME}/captures/paper_orbit/sync_state006.bin"
nohup /home/louis/arb-feed/scripts/paper_orbit.sh \
  >/home/louis/captures/paper_orbit/paper_trig011.log 2>&1 &
echo "started $!"
sleep 2
pgrep -a -f '/home/louis/arb-feed/build/paper_orbit' || echo 'paper_missing'
grep TRIGGER-011 /home/louis/captures/paper_orbit/paper_trig011.log || true
