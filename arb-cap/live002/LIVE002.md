# LIVE-002

Six-venue universe seeded from the 171k trial arbs. No 8-token seed.

`live002.py` walks top-$ our-six txs, collects **every** account on DLMM/Pump/CLMM/CPMM/DAMM/Orca instructions (the pool is rarely `accounts[0]`), keeps accounts whose owner is the venue program, fetches compact state, writes `liveuniv.bin` v2.

Quota so DLMM $ rank cannot crowd the others out: 90/40/40/40/23/23.

CLMM/Orca missing required tick arrays stay fail-closed. Arrays that exist for followed pools are marked `has_ticks=1`.

Wrote `liveuniv.bin` v2: **102 pools** (DLMM 25, Pump 30, CLMM 27, Orca 11, DAMM 9). Tick arrays linked from the 171k txs for 13 CLMM/Orca pools.

CPMM appeared in the seed set (70 program-owned accounts) but every 637-byte pool had a zero or Token-2022-garbled vault tonight. Those keys are not in the snapshot; CPMM quotes stay fail-closed until vault decode is real. Five venues are economically live.

No 8-token seed. Graph is `universe_compile(UNIV_MASK_6)`: pool_idx → pair → 2-hop + 3-hop → `routes_by_pool[]`.
