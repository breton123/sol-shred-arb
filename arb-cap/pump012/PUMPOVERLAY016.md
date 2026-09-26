# PUMP-TX-016

Per-CPI overlay. No deploy. No `N = published vault delta`.

## Identity

```
(sig, outer_ix, inner_ordinal, pool, direction, src_ata, dst_ata, model_version)
```

`model_version = pump-overlay-016`.

## Production rule

```
S_local = AUTH S   # vaults + virtual_quote_reserves + fee config
for each Pump CPI in execution order (outer, then that outer's inners):
    if disc unknown: TX_EXACT = false; fail closed
    S_local = apply(S_local, decoded semantics)
S' = S_local
```

`buy` (`66063d12…`) is **exact-out**: field is `base_amount_out`, not quote-in.
`buy_exact_quote_in` / `sell` stay exact-in.

## Offline replay (4118 Pump mismatches)

Cached txs: 486. Two-leg sell+buy_exact_out: 152.

| residual | n | meaning |
|---|---:|---|
| bit_exact | 168 | single-CPI apply already matches published (V=0 / leftover unexplained) |
| unsupported_cpi | 0 | no unknown Pump disc on recovered legs |
| missing_state | 3679 | AUTH omitted V and/or FEE-015 inputs (2537+1003 class) |
| association_ambiguity | 31 | no Pump CPI recovered for the predicted pool |
| publication_order | 240 | overlay ran, base did not match (or no remap) |

Held-out identity on the **168 wrong-N** with tx bytes:

```
149 / 168  overlay base vault == published
  0 / 168  overlay quote vault == published
  0 fail-closed
```

`n_exec = sell.amount_in − buy_exact_out.amount_in` is the **composition**, not a decoder. Quote still misses because each leg must run FEE-015 (and V when AUTH has it). That is missing_state, not a new N.

## What this freezes

Pump was a stack of representation mistakes, all scoped:

1. virtual omitted  
2. fee schedule omitted  
3. multi-CPI net treated as one N  
4. association keyed `sig+pool`

Do not deploy until overlay + FEE-015 + AUTH virtual are one generation and unexplained residuals are tiny. Then FASTSOAK. Then DLMM.
