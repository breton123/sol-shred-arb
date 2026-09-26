# TRIGGER-012 — Live-hour predecessor dashboard + executed CPI corpus

FUNDED = 0. `classify_n` unchanged. No router allowlist. No CPMM. No invented S'.
1530/1530 RACE_READY is a separate job.

The late-121 corpus stays a regression. This hour is the production coverage question.

## Reference market

Same window as `mev_hour.json`:

| | N | $ |
|---|---:|---:|
| successful DLMM/Pump arbs | 2464 | 2084.60 |

All 2464 winners persisted in `hour_arbs.jsonl`. Slim blocks for all **1674** slots. Causal predecessor = nearest preceding non-vote, non-err, non-arb tx whose resolved program set includes DLMM or Pump (outer **or** inner CPI).

## Dollar funnel

| stage | N | $ | % of $2084.60 |
|---|---:|---:|---:|
| successful DLMM/Pump arbs | 2464 | 2084.6 | 100% |
| causal predecessor identified | 2418 | 2040.5 | 97.9% |
| predecessor tx recovered (RPC) | 2388 | 2037.2 | 97.7% |
| generic FRAMED (full tx present) | 2388 | 2037.2 | 97.7% |
| ALT / loadedAddresses resolved | 2388 | 2037.2 | 97.7% |
| supported DEX actually touched | 2388 | 2037.2 | 97.7% |
| that pool present in current 171-univ | 300 | 621.6 | 29.8% |
| EXACT direct (can construct S') | 1099 | 532.6 | 25.6% |
| EXACT router decoder | 0 | 0.0 | 0% |
| UNPREDICTABLE_PREEXEC | 381 | 301.6 | 14.5% |
| RELEVANT_UNKNOWN / mixed CPI | 685 | 1116.7 | 53.6% |
| pool touched, not in univ (leftover class) | 223 | 86.3 | 4.1% |
| no predecessor in block window | 46 | 44.1 | 2.1% |
| pred tx still missing | 30 | 3.2 | 0.2% |

Shape of identified predecessors:

| shape | N | $ |
|---|---:|---:|
| direct DLMM/Pump | 1335 | 640.1 |
| CPI into DEX | 997 | 1323.6 |

OrbitFlare feed-seen for these predecessor signatures is instrumented (`scan_of_sigs.py`) and was **not** finished in this pass. Until that number exists, “feed-missing” is not a closed bucket. RPC presence ≠ shred presence.

## What this says about the $2k/hr market

The market exists. Almost every dollar has a causal predecessor that **does** invoke Pump or DLMM.

The money does **not** die at framing or ALT. It dies in two places:

1. **Universe recall.** One hour’s executed swap-disc pools: **528 unique**. Current liveuniv: **171**. In-univ intersection: 54 of those 528. 256 is already too small. Favourite-256 cannot represent this market. CORE-009 still holds: hot cost is `routes_by_pool[changed]`, not walking global N. Storage must become a heap generation, not `LIVE_POOL_MAX=256`.

2. **CPI transition inference.** $1324 is routed. Of that, $302 is already **UNPREDICTABLE_PREEXEC** (inner `amount_in` absent from every outer payload). $1117 is still `RELEVANT_UNKNOWN` because the shape is mixed: some inner amounts appear in outer bytes, some do not (multi-leg FLASHX / 6Vo / Jupiter / DF1ow). That is not “we can’t see the tx.” It is “pre-exec fields do not yet give a bit-for-bit N.”

Exact S' is only $533 (direct, and many of those pools are **outside** the 171). Adding FLASHX to `classify_n` would not move this dashboard.

## Executed CPI corpus

`corpus.jsonl` + `router_shapes.json` — group by outer program + discriminator + data length.

Highest-value shapes (this hour):

| outer | disc / len | N | $ | pre-exec amount? |
|---|---|---:|---:|---|
| FLASHX8D… | `01…` / 10 B | 145 | 317 | mixed (multi-leg) |
| 6Vo3245… | `af051981…` / 26 B | 126 | 278 | mixed |
| FLASHX8D… | other 10 B | 9+28+… | ~170 | mixed |
| 6Vo3245… | `f0f3774c…` / 19 B | 20 | 30 | **absent** — same as the historical Mriya-class finding |
| JUP6… | several | ~80 | ~70 | mixed / absent |
| DF1ow… | 143–184 B | | ~80 | mostly absent |

Three outcomes, as specified:

1. **Fully deterministic from outer ix** — no shape in this hour is uniformly `amount_in_outer_bytes` across all legs. No decoder implemented. Correct.
2. **Deterministic with cached S** — not proven yet. Do not guess from vault totals.
3. **UNPREDICTABLE_PREEXEC** — $302 this hour, including 6Vo 19-byte `f0f3774c…`. Raw leader shreds cannot produce exact S' for that shape. That is where Flowra / blockspace / private orderflow would matter, not more IDL archaeology.

The $1117 mixed bucket is the remaining research pile: per-shape, ask whether the **watched-pool** leg’s amount is in the outer bytes even when another hop is not. Do not collapse it into a decoder until that is stable bit-for-bit.

## Universe rule

```
successful market predecessor
    → supported DEX actually touched?
    YES
    → that pool belongs in the universe
```

`required_pools.json`: **528** swap-disc pools, **474** missing from the 171, **over_256=true**.

Top missing (real swap discs, globals GS4CU59 / D1ZN9Wj1 / pfeeUxB6 excluded):

- `9Zach1K…` Pump 149 hits / $307
- `Ax9GpoB…` Pump 73 / $243
- then a long tail of Pump pools the 171 never indexed

Do not solve this by picking 256 favourites. Next storage change: heap `meta[] / pump[] / dlmm.pool[]` with a published generation, load N=1000+ without stack-copy.

## Completion target (not met)

Explain ≥95% of economically significant DLMM/Pump predecessor dollars as:

- exact-predictable, **or**
- provably pre-execution-unpredictable, **or**
- feed-missing, **or**
- unsupported state

Current closed explanation ≈ **exact $533 + unpredictable $302 + no-pred $44 + leftover univ $86 ≈ $966 / 46%**.

The other $1117 is a **named** mixed-CPI corpus, not a mystery. It is still too large to call the hour explained.

OF feed-seen is the missing axis that can move dollars into feed-missing vs detector-missing.

## Independence

| plane | target | this task |
|---|---|---|
| trigger | observe + understand N | dashboard + corpus; architecture from TRIGGER-011 kept |
| execution | 1530/1530 RACE_READY | untouched |

When those meet, the {DLMM, Pump} machine is complete. Not before. No CPMM until then.

FUNDED remains 0.

TRIGGER-012 FAIL — HOUR EXPLAINED AT 46%, UNIVERSE 528>256, CPI MIXED $1117 STILL OPEN
