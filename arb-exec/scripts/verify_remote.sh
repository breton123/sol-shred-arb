#!/bin/bash
set -euo pipefail
export PATH="${HOME}/.local/share/solana/install/active_release/bin:${PATH}"
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
URL="${HELIUS_RPC_URL:-${RPC_URL:-}}"
solana program show 38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K \
  --url "${URL}" \
  --keypair /home/louis/arb-exec/.deploy/wallet.json
sleep 2
bash /home/louis/arb-exec/scripts/go_deploy.sh verify
