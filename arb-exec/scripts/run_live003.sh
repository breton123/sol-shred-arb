#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/exec_live003.py
cp /tmp/exec_live003.py /home/louis/arb-exec/scripts/exec_live003.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
mkdir -p /home/louis/arb-cap/exec_live003
cd /home/louis
python3 /home/louis/arb-exec/scripts/exec_live003.py
