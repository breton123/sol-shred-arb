#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/exec_live002b.py /tmp/oneshot_live.py /tmp/alt_plane.py /tmp/STALE.json
cp /tmp/exec_live002b.py /home/louis/arb-exec/scripts/exec_live002b.py
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/alt_plane.py /home/louis/arb-exec/scripts/alt_plane.py
mkdir -p /home/louis/arb-cap/oneshot
cp /tmp/STALE.json /home/louis/arb-cap/oneshot/STALE.json
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
python3 /home/louis/arb-exec/scripts/alt_plane.py register
