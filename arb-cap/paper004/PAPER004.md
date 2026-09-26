# PAPER-004 — validate the 34

Replay: `paper004` on `liveuniv.bin` + `sync.bin` from the 20-minute session.
Chain: Helius `getSignatureStatuses` / `getTransaction` / vault pre-post.
No send. No Flowra.

## Missing-state (74 / 113)

Replay of all 113 known-pool decides:

| reason | n |
|---|---|
| `DLMM_MISSING_BIN` | **72** |
| `PUMP_APPLY_FAIL` | 2 |
| `NO_OPP` (apply ok, no cycle) | 2 |
| `NO_DLMM_PARTNER` | 2 |
| `NO_PUMP_PARTNER` | 1 |
| `OK` (positive opp) | 34 |

The original 39/113 state-sufficient is apply-ok (`OK` + `NO_OPP` + partner-miss that still `hot_commit`s).
The 74 fail-to-apply are **72 missing-bin + 2 pump apply**. Not other venues, not stale-version, not vault metadata.

`DLMM_CACHE_K = 16` is frozen. After a few committed walks, `active_id` leaves the INIT window and predict fail-closes. Observed on the one hot pool: INIT vs chain `active_id` **-21186 vs -21121** (65 bins). That is already outside ±16.

## The 34 — distribution (SOL @ $121)

Not dust. Also not a healthy book.

| | SOL | $ | after est. fee (105k lamports) |
|---|---|---|---|
| p50 | 61.3 | **$7,415** | $7,415 |
| p90 | 254.7 | **$30,822** | same |
| max | 350.6 | **$42,421** | same |

4 / 34 are small Pump (pool 0): **$0.017, $0.47, $0.50, $0.52**. None of those 4 landed.
30 / 34 are DLMM pool `HTvjzsfX…` (idx 15) quoting $400–$42k.

That is the phantom shape, not the p50=$1.80 book.

## Chain after N

| N landed | 10 |
| N failed (DLMM `Custom 6001`) | 12 |
| unseen / expired | 12 |

`6001` is slip / insufficient-bin on chain — the same family as `DLMM_MISSING_BIN`.

## predicted S' = actual post-N S

**0 / 10** checked equals. 0 close.

Example (landed N `mwSC5UAu…`, slot 450339045):

| | pred S' | chain post-N |
|---|---|---|
| reserve_x | 727,694,829,757 | 679,970,012,108 |
| reserve_y | 352,225,612,435 | 355,581,853,044 |
| active_id | -21186 | -21121 |

We committed N that later 6001-failed, then quoted the next 29 off that poisoned S. That is PAPER-002 chronology again, just live.

Same-slot subsequent arb: **none**. Later DLMM↔Pump touches exist minutes afterward; they are not this slot's searcher.

## Verdict

The 34 do **not** survive the boxed check. Latency is real. The quotes are not.

Next leverage is state, not venues: refresh / widen hot-bin coverage from observed walks, and do not `hot_commit` an N that has not landed.
