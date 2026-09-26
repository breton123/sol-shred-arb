# FAM-6 — DLMM → DLMM

ONESHOT #6 left armed. RabbitStream left running. OUR_EXEC `38dsYLgt…` not upgraded.

## Family-255 breakdown (armed window, ~45 min)

| seq | hops | searchable | mut_auth | cap>0 | best cap | best optimal |
|---|---|---|---|---|---|---|
| **dlmm-dlmm** | 2 | 13 | **6** | 8 | 183784 | 496665456 |
| dlmm-dlmm-dlmm | 3 | 10 | 3 | 5 | 26281 | 38754407 |
| dlmm-dlmm-pump | 3 | 1 | 1 | 1 | 462446 | 35454718 |
| pump-dlmm-dlmm | 3 | 1 | 1 | 0 | 0 | 4992606 |
| (empty / unknown) | 0 | — | — | — | — | — |

Dominant executable-shaped sequence is **DLMM → DLMM**, not DLMM³.
Fattest mut_auth row: idx 160 SOL-USDC DLMM vs a second SOL-USDC DLMM, unconstrained ~0.50 SOL, 0.05-cap 183k.

DLMM³ is the runner-up and can reuse the same swap2 CPI later. Not this gate.

## Why family 255

`route_family_of` only stamped mixed 2-hop proto pairs. Two DLMMs were `ROUTE_FAM_OTHER`.
Compiler already emits SOL → T → SOL 2-hops. We now stamp those `ROUTE_FAM_6_DLMM_DLMM`.

## Short gate (no route0-length DLMM revalidation)

1. Typed mint continuity: SOL → T on pool A, T → SOL on pool B, A ≠ B.
2. Quote: existing `paper_quote_hop` / DLMM kernel. Already producing these rows.
3. Atomic executor: new program `ARBDLMM2`, two `swap2` CPIs, `Custom(6)` on quote.
4. Impossible `min_profit=1e9` must Custom(6) after deploy (not from the #6 wallet).
5. Real hurdle 525k / CU measured on that sim.
6. ALT plane + oneshot eligibility are the step after Custom(6). Not wired to #6.

## Isolation

| thing | status |
|---|---|
| ONESHOT #6 | armed, follow EOF, unchanged |
| OUR_EXEC | frozen, still 2-hop DLMM+Pump |
| program_dlmm2 | new crate, new program id when deployed |
| STATE-007 / SWQOS / Rabbit | untouched |
| paper.c / hot.c / cycle.c / dlmm.c | not mutated |
| paper_orbit exec_fam | local source only; live binary not rebuilt |

## Next after Custom(6) on a new program id

- ALT plane for FAM-6 templates
- New oneshot follower, not a patch to #6
- Size: 0.05 is a first-proof cap, not a strategy cap
- Then DLMM³ on the same CPI helper if that sequence stays #2
