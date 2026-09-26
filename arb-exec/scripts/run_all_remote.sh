#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/exec_live002b.py
cp /tmp/exec_live002b.py /home/louis/arb-exec/scripts/exec_live002b.py
python3 -c 'import solders; print("solders_ok")'
mkdir -p /home/louis/arb-cap/exec_live002b
exec bash /home/louis/arb-exec/scripts/go_deploy.sh all
