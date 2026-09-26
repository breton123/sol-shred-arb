# arb-exec

Turn an `opportunity_t` into signed transaction bytes ready to send.

```text
arb-core    opportunity_t
arb-exec    signed tx bytes
```

This tree does not quote, size, or predict. Live last hop is SWQOS QUIC
(`swqos_send`). Frozen `leader_send()` is still the local-loopback proof.

```text
EXEC-001            route-0 executor + local proof     FROZEN  account layout
EXEC-002            unsigned tx template + patch       FROZEN  offsets
EXEC-003            Ed25519 sign of frozen message     FROZEN  libsodium
EXEC-004            durable nonce pool                 FROZEN  64-slot ring
EXEC-005            leader_send stub                   FROZEN  local UDP
EXEC-005A           funded mainnet smoke               memo + durable nonce
EXEC-LIVE-001       live route0 program                pinocchio + real CPI
```

See `arb-cap/exec_live001/EXEC-LIVE-001.md`. Program source is `arb-exec/program`.
Frozen `route0.c` / account order / EXEC-002 template were not mutated.

## EXEC-LIVE-002B

New v0 + one ALT template. EXEC-002 stays frozen. Logical OUR_EXEC order is
still the 35 EXEC-001 slots; bitmap/host optional-none is the DLMM program id.

```bash
cd ~/arb-exec
cmake --build build --target exec_v0 && ./build/exec_v0
python arb-exec/scripts/exec_live002b.py
```

Hot path: `route0_v0_compile` → `route0_v0_patch` → `route0_v0_sign` (554-byte
v0 message slice). Wire size **619 B** (margin 613). RPC accepted the packet;
simulate is `ProgramAccountNotFound` until loader-v3 deploy. Never BPF Loader 2.

## EXEC-LIVE-002

Bake the LIVE-001 pair into the frozen 35-account template. Order is the lock.
Control plane resolves real pools/vaults/bins/oracle/fees/ATAs/OUR_EXEC, then
`route0_tx_compile` → patch → sign → `simulateTransaction`. Never sends the arb.

```bash
python arb-exec/scripts/exec_live002.py
```


## EXEC-001

Smallest real transaction for route 0:

```text
our wallet
   ↓
OUR_EXEC
   ↓
DLMM swap
   ↓
Pump swap
   ↓
final balance
   ↓
profit >= min_profit
      ├─ yes → success
      └─ no  → revert
```

Both directions. `amount_in` and `direction` come from `opportunity_t`. Output returns to our quote inventory. A stale or unprofitable second leg reverts the first. Account order is deterministic. Local CU is recorded.

Live DLMM / Pump replace the shims. They do not reorder accounts.

```bash
cd ~/arb-exec
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
./build/exec001
```

EXEC-001 is frozen. Do not change `route0_process`, `route0_pack`, or the account table in `route0.h`.

## EXEC-002

Offline: bake the 35-account vector, OUR_EXEC, ComputeBudget, CU-limit ix, and route0 skeleton into `route0_tx_template`. Pump base/quote mints alias DLMM X/Y. No ALT.

Hot path: memcpy the template, then patch five constant offsets — `amount_in`, `direction`, `min_profit`, blockhash/nonce, CU price. No heap, no metas, no pubkey encode.

```bash
cd ~/arb-exec
cmake --build build
./build/exec002 --cpu 47 --mlock
```

EXEC-002 is frozen. Do not change `route0_tx_compile`, `route0_tx_patch`, or the offset constants.

## EXEC-003

Solana signs the message, not the tx. Offsets are fixed: signature at 1, message at 65, length 1240.

Signer is prepared once (libsodium 1.0.18, seed→expanded sk, mlock). Hot path is `crypto_sign_ed25519_detached` into the signature slot. OpenSSL 3 verifies independently. No keyfile or heap on the sign path. Test keys are getrandom, never committed.

```bash
cd ~/arb-exec
cmake --build build
./build/exec003 --cpu 47 --mlock
```

libsodium wins (~15 µs p50). OpenSSL is ~2× on the same 1240-byte message. Same-message vs patched is the same cost. `T(opportunity → signed tx) ≈ T(Ed25519)`.

EXEC-003 is frozen. Do not change `route0_sign` or the message/signature offsets.

## EXEC-004

64-slot durable nonce ring. One exec thread, no locks. Control plane loads hashes and reloads after IN_FLIGHT → REFRESH. Hot path is `nonce_claim` → READY hash. Patch that hash into the frozen blockhash slot. No RPC on the claim path. Not 992.

```bash
cd ~/arb-exec
cmake --build build
./build/exec004 --cpu 47 --mlock
```

Claim is 84 cycles (20 ns). Noise next to the signature. EXEC-004 is frozen. Do not change `nonce_claim` or grow the pool to 992.

## Control plane

`nonce_load` × 64 → READY. Attempt `nonce_claim` → IN_FLIGHT. Confirm or fail
`ctrl_nonce_finish` → `nonce_reload` → READY. RPC is the script that writes
`ctrl.bin` (`nonce_ctrl.py`). The opportunity path never opens a socket.

Fees are the same split: `ctrl_fees_set(cu_price, min_profit)` on the plane,
`ctrl_patch` on the hot path. It only stores into the frozen CU-price and
`min_profit` offsets.

```bash
python arb-exec/scripts/nonce_ctrl.py --cu-price 1000 --min-profit 1
# with 64 initialized nonce accounts:
# python arb-exec/scripts/nonce_ctrl.py --pubkeys nonces.txt --cu-price 1000 --min-profit 1
cd ~/arb-exec && cmake --build build --target exec_ctrl && ./build/exec_ctrl
```

## EXEC-005

`leader_conn_t leaders[LEADER_N]` and `leader_send(conn, tx, len)`. Connected UDP, opened on the control plane. Local loopback only. Do not turn this into a public TPU client. DoubleZero replaces it.

```text
opportunity → nonce → patch → sign → leader_send()
```

```bash
cd ~/arb-exec
cmake --build build
./build/exec005
```

EXEC-005 is frozen. Do not grow `leader_send`. Live send is SWQOS:

```text
opportunity → nonce → patch → sign → swqos_send()
```

```bash
# SWQOS_KEY or SWQOS_API_KEY in .env / ~/.arb-swqos.env
cd ~/arb-exec
cmake --build build --target exec_swqos
./build/exec_swqos
```

`swqos_open()` holds two QUIC connections to `send.swqos.com:11000`
(ALPN `ultrasend/1`). Hot path opens one stream, writes the raw ≤1232 B
tx, finishes, returns. Receipt drain is off-path. Never reconnect per send.

## EXEC-005A

Funded mainnet smoke. Harmless memo, then one durable-nonce memo. Our bytes, our signer. RPC `sendTransaction` lands them (mainnet TPU is QUIC; UDP TPU is gone). Not the arb. Not live DLMM/Pump.

Keys and RPC URL come from `SMOKE_ENV` / `~/.arb-smoke.env`. Never commit them.

```bash
cd ~/arb-exec
cmake --build build
./build/exec005a
```

Landed on mainnet (our bytes, our signer):

```text
A  memo          5wMEJxcS...G45GKn   slot 449845732
   create-nonce  2jgTCsSr...g6PRc    slot 449845736
B  nonce-memo    2mqYqNQj...P7gNw    slot 449845887
```


## Layout

```text
include/     opportunity  route0  tx_template  sign  nonce  leader
src/         route0.c  tx_template.c  sign.c  nonce.c  leader.c
tests/       exec001–exec005
```



