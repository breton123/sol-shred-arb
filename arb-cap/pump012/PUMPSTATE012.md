# PUMP-STATE-012

Representation/publication fix. `pump_apply_swap` is unchanged.

AUTH now carries the fields the kernel already reads:

- `reserve_base` = `base_vault_amount`
- `reserve_quote` = `quote_vault_amount`
- `virtual_quote` = `Pool.virtual_quote_reserves` (i128 at byte 245; 0 on legacy)

`Y_effective = quote_vault_amount + virtual_quote_reserves` is derived only inside apply/quote. Virtual is not pre-folded into `reserve_quote`.

Offline gate (frozen soak, no deploy):

1. Replay Pump mismatches with inverted/filled virtual.
2. `virtual_reserve_config` cluster → explained.
3. `wrong_transaction_association` stays a separate issue.
4. V=0 successes stay exact.

Offline replay of the frozen 4118 Pump mismatches (no live deploy):

| bucket | n |
|---|---:|
| virtual both-vaults bit-exact | 2537 |
| virtual prices base, quote fee left | 1003 |
| virtual/config explained | **3540** |
| wrong association | 103 |
| wrong N (sell base ≠ amount_in) | 168 |
| unexplained | 307 |
| new regression | 0 |

The 1003 leftover quote deltas are pool fee/config (likely `Pool.creator_fee_bps`), not AUTH folding. 168 are bad N. Do not treat those as STATE-011.

Then a fresh state generation. Not STATE-011. Not DLMM-FEE-012 yet.
