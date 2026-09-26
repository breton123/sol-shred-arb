#!/bin/bash
set -euo pipefail
export PATH="${HOME}/.local/share/solana/install/active_release/bin:${PATH}"
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
PY=/home/louis/arb-exec/.venv/bin/python
cd /home/louis
exec "${PY}" /home/louis/arb-exec/scripts/go_deploy.py simulate
