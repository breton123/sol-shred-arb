#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/dump_pump24_full.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
python3 /tmp/dump_pump24_full.py
