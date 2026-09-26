# EXEC-LIVE-002B — v0 + ALT route0

EXEC-002 legacy template stays frozen at 1305 B. New path is
`route0_v0_compile` → patch → `route0_v0_sign` over the 554-byte v0 slice.

## Gate

| check | result |
|---|---|
| v0 message compiles | yes (`exec_v0` on Frankfurt) |
| ALT populated with live route accounts | `6x83bLBvd4P8w9tUvoMMWvXUJpTmRjn2mcZ27o6hyDDj` (23 addrs) |
| logical OUR_EXEC order unchanged | 35 EXEC-001 slots; bitmap/host = DLMM program id |
| serialized tx < 1232 B | **619 B** (b64 828, margin 613) |
| libsodium signs correct v0 slice | `exec_v0` verifies; tamper fails |
| RPC accepts bytes for simulation | **yes** — `ProgramAccountNotFound`, `unitsConsumed=0` |

`ProgramAccountNotFound` is OUR_EXEC (`38dsYLgt…`) not on-chain. The packet
parsed. The ALT resolved. Simulation is now the debugger.

## Six missings (from EXEC-LIVE-002)

| slot | 002 | 002B |
|---|---|---|
| 2 user_base | invented-missing ATA | created Token-2022 ATA `8tna1fc2…` |
| 10 bitmap | invented PDA | optional-none = DLMM program |
| 14 host_fee | invented PDA | optional-none = DLMM program |
| 23 fee_config | missing `GQy76sRy…` | live `5PHirr8j…` (pfee, 4097 B) |
| 32 creator_auth | missing PDA | same real PDA `F2Ne1XNs…` — live sells use it uninitialized |
| 34 user_vol | uncreated | same real PDA `GWMcD1Hj…` — not a dummy |

No dummy PDAs. Empty creator_auth / user_vol stay as derived addresses.

## Custom(6) — blocked on deploy

`amount_in=10000`, `min_profit=1e9` is ready. Wallet has WSOL and the Token-2022
ATA. Loader-v3 deploy of `38dsYLgt…` is still tomorrow (≥0.15 SOL). Do not use
BPF Loader 2.

Live Pump sell is now **24** metas (was 22): fee_config @19, pfee @20, then two
trailing extras. Adapter update is after the program is executable — do not
conflate with the size gate.

## Leftover ALTs

First two tables were superseded, deactivated, and closed (rent back).
Keep `6x83bLBv…` (23 live route accounts). Wallet leftover ≈ 0.015 SOL.
