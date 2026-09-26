#!/bin/bash
# Upgrade OUR_EXEC with Buy 26-meta CPI. Sell 24-meta stays valid. Then sim dir=1.
# Does not stop ONESHOT. Never sends the arb.
set -euo pipefail
export PATH="${HOME}/.cargo/bin:${HOME}/.local/share/solana/install/active_release/bin:${PATH}"
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-exec/program/src/lib.rs \
  /home/louis/arb-exec/scripts/exec_live002b.py
cp /home/louis/arb-exec/program/src/lib.rs /home/louis/arb-exec-live/program/src/lib.rs
cd /home/louis/arb-exec-live/program
cargo-build-sbf
mkdir -p /home/louis/arb-exec/program/target/deploy
cp -f /home/louis/arb-exec-live/program/target/deploy/route0.so \
  /home/louis/arb-exec/program/target/deploy/route0.so
bash /home/louis/arb-exec/scripts/go_deploy.sh deploy
bash /home/louis/arb-exec/scripts/go_deploy.sh verify
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
export SIM_DIR=1
cd /home/louis
python3 /home/louis/arb-exec/scripts/exec_live002b.py
python3 - <<'PY'
import json
from pathlib import Path
r = json.loads(Path("/home/louis/arb-cap/exec_live002b/report.json").read_text())
sim = r.get("simulate") or {}
print("DIR1_SIM err", sim.get("err"))
print("DIR1_SIM cu", sim.get("cu"))
print("DIR1_SIM tx", r.get("tx_len"), "margin", r.get("margin"))
for line in (sim.get("logs") or [])[-20:]:
    print(line)
PY
