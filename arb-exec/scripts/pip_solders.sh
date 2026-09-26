#!/bin/bash
set -euo pipefail
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3 /tmp/get-pip.py --user --break-system-packages
python3 -m pip install --user --break-system-packages solders
python3 -c 'import solders; print("solders_ok")'
