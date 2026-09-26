# Control plane — nonce ring + fees

EXEC-004 is frozen. This is the boring production side around it.

```
nonce_load × 64     → 64 READY
nonce_claim         → IN_FLIGHT     (opportunity path, no RPC)
confirm / fail      → nonce_reload  → READY
```

`ctrl_fees_set(cu_price, min_profit)` at startup or whenever the plane updates.
Hot path is `ctrl_patch`: those two numbers plus the claimed hash go into the
frozen offsets. No RPC, no fee fetch, no tip math.

RPC is `arb-exec/scripts/nonce_ctrl.py`. It writes `ctrl.bin` (CTL1, 64 pubkey+hash
records + the two fee numbers). C only `nonce_load` / `nonce_reload`.

Does not create 64 durable-nonce accounts. Pass `--pubkeys` when those exist.

```
python arb-exec/scripts/nonce_ctrl.py --cu-price 1000 --min-profit 1
./build/exec_ctrl
```
