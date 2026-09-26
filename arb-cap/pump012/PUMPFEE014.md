# PUMP-FEE-014

Quote-token conservation on the 704 unexplained `buy_exact_quote_in` residuals. No deploy. No fitted global bps.

## Class still holds

| | n |
|---|---:|
| pool creator 100/300 | 240 |
| proto-only debit | 59 |
| unexplained | 704 |
| sell regression | 0 |

Token program on 246 fetched unexplained txs: **Tokenkeg only**. Not Token-2022.

## Conservation (idx 399 example)

`spendable 126477 = vault 124940 + 581 + 581 + 375`

The three extra credits are WSOL ATAs owned by:

- `5eHhjP8JaYkz83CWwvGU2uMUXefd3AazWGx4gpcuEEYD` (CASRL2zk…)
- `G5UZAVbAf46s7cKWoyKu8kYTip9DGTpbLZ2qa9Aq69dP` (BWXT6RUh…) — already a Pump `protocol_fee_recipient` in hops goldens
- `3reMEVcjHcpLYyPjv35gvqzGRThcbABRtzR538ZNJSyG` (HqH4dNGy…)

That same triple appears on **106** cached txs (the idx 399 set). Vault credit equals published vault delta. Kernel proto+creator was 128; actual ATA take was 1537; `1537 − 128 = 1409 = residual`.

The missing ~90–111 bps is **not a vault accounting bug**. It leaves the user spend into **Pump fee-recipient ATAs** (and the fee program `pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ` seen on Pump CPI). LP stays in the pool; these do not.

## Predicate (do not fit 111)

No pool has a single `ceil(spendable * bps / 10000)` that hits every row. Per-pool mode is tight (399: 112 bps, 102: 79, 171: 89) because **recipient take / spendable** is stable per pool, not because 111 is a config constant.

What partitions the 704:

- `Pool.creator_fee_bps = 0`
- `holder = 0` on 633
- quote mint **WSOL**
- `virtual_quote_reserves ≈ 17584505xxx` (same 1.758e10 band as PUMP-012 invert)
- fee program / extra protocol recipients credited

idx 68 is the exception in the top list: virt=0, holder=1.

## Frozen observation (not a kernel patch yet)

```
spendable = pool_quote_vault_delta + Σ protocol/pfee ATA credits
residual = Σ ATA credits − kernel(proto + creator)
```

Replay of the 704 waits on reading `pfee` / GlobalConfig recipient rates so AUTH can debit the same set. Do not treat 111 as a field.

Next: PUMP-N-015 (168 wrong N), then association. Not DLMM.
