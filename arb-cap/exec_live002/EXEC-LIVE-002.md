# EXEC-LIVE-002 — live accounts in the frozen template

`route0.h` order and `route0_tx_compile` were not mutated.

LIVE-001 pair baked into the 35-account vector, compiled, signed, simulated.

```
DAErPzgi  DLMM
BRjMA8UA  Pump
HHNzjTAB  authority / fee payer
38dsYLgt  OUR_EXEC  (v3 key, not deployed)
```

## Compile

Frozen C `exec_live002` on Frankfurt and the Python baker produced the **same 1305 bytes**.

| lock | value |
|------|--------|
| unique keys | 35 (33 route + OUR_EXEC + ComputeBudget) |
| mint aliases | Pump base=DLMM X, Pump quote=DLMM Y |
| writable unique | 15 |
| readonly unsigned | 20 |
| signers | 1 (authority) |
| ix | `ARBEXEC0` dir=0 amount=10000 min_profit=1 |

Optional DLMM slots are real PDAs (`bitmap`, `host_fee`), not the DLMM program id. Extra aliases would have dropped unique-key count below 35 and the frozen compiler would reject.

## Accounts on-chain now

29 / 35 exist. Missing (not created yet, or unused optional PDAs):

| idx | name | why |
|-----|------|-----|
| 2 | user_base | Token-2022 ATA not created |
| 10 | dlmm_bitmap | pair has no extension |
| 14 | dlmm_host_fee | optional none — unique PDA so compile can lock |
| 23 | pump_fee_config | copied from a live Pump ix; account not present |
| 32 | pump_creator_auth | same |
| 34 | pump_user_vol | our volume PDA not created |

Those do not break compile. They would fail inside a real CPI if the callee requires them.

## Simulate

```
raw 1305  >  wire max 1232
b64 1740  >  encoded max 1644
```

RPC: `VersionedTransaction too large`. No program invoke. No CU. No signer/writable runtime check.

The frozen legacy template cannot be simulated or landed. Deploying OUR_EXEC tomorrow does not fix this. The 35-key message is 73 bytes over the packet limit.

## What this caught before money

Not a bad meta flag — the packet itself is illegal.

Writable/signer layout is internally consistent with EXEC-002. Mainnet never loaded it.

A sendable route0 needs an ALT (or fewer unique keys). That is a new template, not a patch of this one. EXEC-002 stays frozen.

Keys: `arb-cap/exec_live002/keys.json`. Signed bytes: `signed.tx` (gitignored if you add it; report is the record).
