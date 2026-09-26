#!/bin/bash
# Rebuild route0.so and upgrade loader-v3. Never sends the arb.
set -euo pipefail
export PATH="${HOME}/.cargo/bin:${HOME}/.local/share/solana/install/active_release/bin:${PATH}"
python3 /home/louis/arb-cap/state005/crlf.py /home/louis/arb-exec/program/src/lib.rs
cp /home/louis/arb-exec/program/src/lib.rs /home/louis/arb-exec-live/program/src/lib.rs
cd /home/louis/arb-exec-live/program
cargo-build-sbf
mkdir -p /home/louis/arb-exec/program/target/deploy
cp -f /home/louis/arb-exec-live/program/target/deploy/route0.so \
  /home/louis/arb-exec/program/target/deploy/route0.so
ls -l /home/louis/arb-exec/program/target/deploy/route0.so
bash /home/louis/arb-exec/scripts/go_deploy.sh deploy
bash /home/louis/arb-exec/scripts/go_deploy.sh verify
bash /home/louis/arb-exec/scripts/go_deploy.sh simulate
bash /home/louis/arb-exec/scripts/go_deploy.sh walk
