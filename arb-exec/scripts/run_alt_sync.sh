#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/exec_live002b.py /tmp/oneshot_live.py /tmp/alt_plane.py
cp /tmp/exec_live002b.py /home/louis/arb-exec/scripts/exec_live002b.py
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/alt_plane.py /home/louis/arb-exec/scripts/alt_plane.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
python3 /home/louis/arb-exec/scripts/alt_plane.py sync
