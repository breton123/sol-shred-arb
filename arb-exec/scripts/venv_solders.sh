#!/bin/bash
set -euo pipefail
python3 -m venv /home/louis/arb-exec/.venv
/home/louis/arb-exec/.venv/bin/pip install solders
/home/louis/arb-exec/.venv/bin/python -c 'import solders; print("solders_ok")'
