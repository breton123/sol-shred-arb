# arb-exec

Turn an `opportunity_t` into signed transaction bytes ready to send.

```text
arb-core    opportunity_t
arb-exec    signed tx bytes
```

This tree does not quote, size, or predict. It does not open sockets. Signing, nonce, and landing come after the on-chain route is proven.

```text
EXEC-001            route-0 executor + local proof     FROZEN  account layout
later               sign / nonce / send
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

## Layout

```text
include/     opportunity  route0
src/         route0.c
tests/       exec001
```
