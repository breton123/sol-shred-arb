#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/oneshot_live.py \
  /home/louis/arb-exec/scripts/run_oneshot.sh
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
rm -f /home/louis/arb-cap/oneshot/ARMED
if pgrep -f '/home/louis/arb-exec/scripts/oneshot_live.py' >/dev/null; then
  echo "oneshot still running"
  exit 75
fi
bash /home/louis/arb-exec/scripts/run_oneshot.sh
