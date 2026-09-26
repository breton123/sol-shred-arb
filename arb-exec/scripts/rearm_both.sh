#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/oneshot_live.py \
  /tmp/WALK_DIR1.json
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
mkdir -p /home/louis/arb-cap/exec_live002b
cp /tmp/WALK_DIR1.json /home/louis/arb-cap/exec_live002b/WALK_DIR1.json
rm -f /home/louis/arb-cap/oneshot/ARMED
pgrep -af oneshot || echo "no oneshot"
export PATH="${HOME}/.local/share/solana/install/active_release/bin:${PATH}"
solana balance HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX --url https://api.mainnet-beta.solana.com
