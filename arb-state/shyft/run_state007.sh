#!/bin/bash
# Long-running STATE-007. Independent of PAPER. FUNDED is not this process.
set -euo pipefail
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
if [[ -f /home/louis/.arb-state007.env ]]; then
  # shellcheck disable=SC1091
  . /home/louis/.arb-state007.env
fi
set +a
exec python3 /home/louis/arb-state/shyft/state007.py
