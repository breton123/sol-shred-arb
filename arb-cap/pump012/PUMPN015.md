# PUMP-N-015

Wrong-N sells (168) and association (103). No deploy. No generic `amount_in`.

All 168 are tagged direction=sell. Executed N is the **published base vault delta**, not the decoded sell field.

## Frozen rules (held-out 36/40 classified)

| class | n | rule |
|---|---:|---|
| **N_PREVIOUS_OUTPUT** | **149** | Same pool, same tx: `sell` + `buy_exact_out`. `n_exec = sell.amount_in − buy_exact_out.amount_in` (sign follows net). Predicted N is the **sell literal**. AUTH applied one leg; publication is the **net**. |
| **N_CLAMPED** | **5** | `n_exec = published_base − before_base`, `0 < n_exec < encoded`, `apply(n_exec)` hits published base. Encoded is requested; fill is smaller. No second Pump exact-out on that pool. |
| **N_UNKNOWN** | **14** | Fail closed. Includes sells whose published base **decreased** without a recovered two-leg identity, and sells where encoded **<** executed (e.g. idx 399: ix 190949443 vs vault +2098510000). Do not invent N. |
| N_LITERAL | 0 | Encoded already equals executed (these never enter wrong-N). |
| N_BALANCE_DERIVED | 0 | No held-out row needed a source-ATA debit distinct from the two-leg net. |
| N_INVERSE_QUOTE | 0 | Quote-vault invert is not the executed base. |

Example (first row):

```
sell          11_411_288_817
buy_exact_out 11_345_137_575
n_exec           66_151_242   = sell − buy_exact_out
n_pred        11_411_288_817  = sell ix only
```

Negative `n_exec` is the same identity with `buy_exact_out > sell`. That is not a clamp.

**Correction, not a new mystery bps:** apply **every** Pump CPI on the pool (outer ix index + inner ordinal), or fail closed on multi-leg nets. One `amount_in` per signature+pool is wrong.

## Association (103)

| class | n | rule |
|---|---:|---|
| **ASSOC_SINGLE_LEG** | **58** | One Pump CPI on this pool and vaults **moved**. Shadow bucket is too coarse. Anchor `(outer_ix, inner_ordinal, pool, direction, src ATA, dst ATA)`. |
| **ASSOC_MULTI_POOL_TX** | **14** | ≥2 Pump pools in the tx; this pool has one leg. Same anchor; do not key on signature alone. |
| **ASSOC_UNKNOWN** | **31** | No recovered Pump ix in the cached tx (wrapper / missing data). Fail closed. |

Not “random mismatch.” Jupiter wraps Pump as inner CPI. Matching `accounts[0]==pool` without ordinal picks the wrong write or a net.

## What not to do

Do not replace sell `amount_in` with vault delta in the decoder (that hides multi-leg). Do not deploy. 2537 virtual-exact and 968 fee-exact buys stay the regression gate.

## After this

Replay the 4118 with: virtual AUTH + FEE-015 schedule + **per-CPI N** (or fail-closed on sell+buy_exact_out nets) + association by ix ordinal. Then a new AUTH generation only if unexplained residuals are tiny and classified.
