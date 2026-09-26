#!/bin/bash
# STATE-008. Independent of recover_pda3. FUNDED stays 0.
set -euo pipefail
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
if [[ -f /home/louis/.arb-state007.env ]]; then
  # shellcheck disable=SC1091
  . /home/louis/.arb-state007.env
fi
set +a
exec python3 /home/louis/arb-state/shyft/state008.py
