#!/bin/bash
set -euo pipefail
if python3 -c 'import solders' 2>/dev/null; then
  echo solders_ok
  exit 0
fi
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3 /tmp/get-pip.py --user
python3 -m pip install --user solders
python3 -c 'import solders; print("solders_ok")'
