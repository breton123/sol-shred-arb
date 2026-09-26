#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/exec_live002b.py
cp /tmp/exec_live002b.py /home/louis/arb-exec/scripts/exec_live002b.py
export PATH="${HOME}/.local/share/solana/install/active_release/bin:${PATH}"
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
cd /home/louis
python3 /home/louis/arb-exec/scripts/go_deploy.py simulate
python3 /tmp/dump_sim.py
