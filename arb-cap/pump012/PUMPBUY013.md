# PUMP-BUY-013

Reducer only. No deploy. `pump_apply_swap` unchanged.

The 1003 are all `buy_exact_quote_in` (direction 0). Exact-out `buy` is already fail-closed. Sells in the 2537 stay bit-exact (2251 replayed, 0 fail).

## What the quote-vault residual is not

No single Global bps, LP identity, or ceil/floor of `amount_in` / `effective` covers the 1003. `formula_hits` was 0.

## What it is

Kernel buy vault debit today:

`Y' = Y + spendable - proto(effective) - creator(effective)`

with **Global** `creator_fee_bps=5` on every pool. Live `Pool.creator_fee_bps` (i64 at 261) is often 0, sometimes 100/300.

| class | n | note |
|---|---:|---|
| live `Pool.creator_fee_bps` in the same identity | 240 | 100 and 300 bps pools; DJT 181 of these |
| vault `+= spendable - proto` only | 59 | idx 216, `virt=0`, pool creator=0; residual = −global creator |
| pool creator=0 exact | 5 | |
| **still unexplained** | **704** | 633 of those: creator=0, holder=0 |
| sell regression | 0 | |

304 / 1003 (30%) collapse onto “use pool creator field, not Global 5.” The other 70% is a **second** buy-side hole: extra leave clustered near **90 / 111 bps** of `amount_in`, not `Pool.creator_fee_bps` (on-chain field is 0). idx 399 alone is 105 rows at ~111 bps.

Fee debit: protocol and creator are meant to leave the user spend before the pool vault. On 216 they must not both leave. On 100/300 pools they do, at the **pool** rate. On the 633, neither the Global-5 identity nor the pool-0 identity matches committed vault delta.

## Acceptance

**Not met.** One frozen formula does not explain the 1003. Do not deploy PUMP-STATE-012 or a buy-fee patch.

## Next

1. Identify the ~90 bps instrument on creator=0 WSOL pools (event `coin_creator_fee` vs `user_quote_amount_in` vs `quote_amount_in_with_lp_fee`).
2. Then PUMP-N-014 (168 wrong N).
3. Replay all 4118 only after buy residuals are one formula.
