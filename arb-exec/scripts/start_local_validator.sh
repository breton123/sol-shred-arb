#!/bin/bash
set -euo pipefail
export PATH="/home/louis/.local/share/solana/install/active_release/bin:$PATH"
RPC=$(cat /tmp/arb-rpc.url)
LEDGER=/tmp/exec-live001-ledger
rm -rf "$LEDGER"
CLONES=()
while read -r k; do
  [ -z "$k" ] && continue
  case "$k" in
    11111111111111111111111111111111) continue ;;
    TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA) continue ;;
    TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb) continue ;;
    ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL) continue ;;
    MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr) continue ;;
    ComputeBudget111111111111111111111111111111) continue ;;
  esac
  CLONES+=(--clone "$k")
done < /tmp/clone_keys.txt

exec solana-test-validator \
  --reset \
  --ledger "$LEDGER" \
  --rpc-port 8899 \
  --url "$RPC" \
  --clone-upgradeable-program LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo \
  --clone-upgradeable-program pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA \
  --clone-upgradeable-program pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ \
  "${CLONES[@]}"
