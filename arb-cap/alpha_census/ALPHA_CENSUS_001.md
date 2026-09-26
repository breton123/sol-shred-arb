# ALPHA-CENSUS-001

Census of DLMM and Pump state changes, built from transactions that invoked those programs, not from transactions that preceded a known arbitrage.

No transactions were sent. Production search, funded path, executor, STATE-007, OrbitFlare, and SWQOS were not modified.

## Window

Shyft `getSignaturesForAddress` on the DLMM program (`LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo`) and Pump AMM (`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`), newest first, capped at 20,000 signatures each.

| | DLMM | Pump |
|---|---:|---:|
| Signatures paged | 20,000 | 20,000 |
| Failed (`err != null`) | 7,392 | 5,522 |
| Successful txs fetched and classified | 700 | 700 |

Those 1,400 successful transactions sit in slots **450458741–450458929** (188 slots) and block times **1790367738–1790367787** (49 seconds). The 45-minute target was not reached: 20,000 recent program mentions already fill that head-of-chain slice. Figures below are for this slice only. They are not scaled to an hour or a year.

MEV.live over the same block-time span, used only as a control: **543** successful arbs, **$40.08**. That is captured profit in the window, not edge created by the sampled transactions.

## How a transaction was classified

Anchor `Program log: Instruction:` lines were read only while that program was the top of the invoke stack. Names were matched to the published IDLs (`dlmm_idl.json`, 76 instructions; `pump_idl.json`, 32 instructions).

A signature that merely lists the program in its account keys, and never invokes it, is `no_invoke`. That bucket is the background rate for the later taker join.

## Mutation taxonomy

Effect labels describe whether the instruction writes fields the current quote kernels read. They are not measured quote deltas. DLMM quotes read bin amounts, `active_id`, bin step, static fee parameters, and the volatility accumulator. Pump quotes read base/quote reserves, virtual quote, and fee bps. Unclaimed fee balances are not an input. SPL vault balances are not DLMM liquidity.

### Swaps — PRICE_MOVING

| Program | Instructions |
|---|---|
| DLMM | `swap`, `swap2`, `swap_exact_out`, `swap_exact_out2`, `swap_with_price_impact`, `swap_with_price_impact2` |
| Pump | `buy`, `buy_exact_quote_in`, `sell` |

Direct swaps with the amount in the instruction are `PREEXEC_EXACT` once the pool is resolved and local bin or reserve state is cached. Router CPI that only names the pool is `POSTEXEC_ONLY` for size. `swap_exact_out` / `swap_exact_out2` are not decoded by the current swap instruction parser.

### Liquidity — DEPTH_MOVING

Spot can stay put while `quote(size)` changes.

DLMM: `add_liquidity`, `add_liquidity2`, `add_liquidity_by_strategy`, `add_liquidity_by_strategy2`, `add_liquidity_by_strategy_one_side`, `add_liquidity_by_weight`, `add_liquidity_by_weight2`, `add_liquidity_one_side`, `add_liquidity_one_side_precise`, `add_liquidity_one_side_precise2`, `remove_liquidity`, `remove_liquidity2`, `remove_liquidity_by_range`, `remove_liquidity_by_range2`, `remove_all_liquidity`, `rebalance_liquidity`, `close_position`, `close_position2`, `place_limit_order`, `cancel_limit_order`.

Pump: `deposit`, `withdraw`.

`close_position_if_empty` is **NON_PRICING**: the position is already empty. `PREEXEC_DETERMINISTIC_WITH_STATE` if the position shares and the touched bin arrays are already cached. Without those accounts the resulting curve is not known from the outer bytes alone.

### Pool lifecycle — ROUTE_CAPACITY_MOVING

DLMM: `initialize_lb_pair`, `initialize_lb_pair2`, `initialize_permission_lb_pair`, `initialize_customizable_permissionless_lb_pair`, `initialize_customizable_permissionless_lb_pair2`, `set_pair_status`, `set_pair_status_permissionless`, `set_activation_point`.

Pump: `create_pool`, `disable`.

A new pool does not create a cycle until it is in the route graph and has reserves. `PREEXEC_PARTIAL`.

### Fees — FEE_MOVING only when the quote’s fee inputs change

FEE_MOVING: `update_base_fee_parameters`, `update_dynamic_fee_parameters`, `update_fee_config`, `update_creator_fee_config`.

NON_PRICING for this kernel: `claim_fee`, `claim_fee2`, `claim_reward`, `claim_reward2`, `withdraw_protocol_fee`, `zap_protocol_fee`, `collect_coin_creator_fee`, `claim_cashback`, `claim_token_incentives`, `transfer_creator_fees_to_pump`, `transfer_creator_fees_to_pump_v2`. These move accrued balances the swap quote does not read.

### Admin / bins

PRICE_MOVING: `go_to_a_bin` (writes `active_id`). Needs the destination bin’s liquidity already cached: `PREEXEC_DETERMINISTIC_WITH_STATE`.

NON_PRICING until a later liquidity instruction fills them: `initialize_bin_array`, `initialize_bin_array_bitmap_extension`, `increase_oracle_length`, `initialize_position`, `initialize_position2`, `increase_position_length`, `increase_position_length2`, `decrease_position_length`.

`update_fees_and_rewards` refreshes reward checkpoints. It is NON_PRICING unless it also writes fee parameters the kernel reads. Not observed here, left UNKNOWN rather than forced into FEE_MOVING.

### Token / vault events

A transfer that changes a Pump reserve changes the Pump quote (PRICE_MOVING and DEPTH_MOVING). A transfer into a DLMM vault does **not** change the DLMM quote unless bin amounts change. This census did not walk vault accounts. See limitations.

### What actually executed in the 49-second slice

Instruction counts below are occurrences inside transactions that invoked the program. One transaction can contribute several names.

**DLMM, 112 invoking transactions** out of 700 mentions:

| Instruction | n | Effect |
|---|---:|---|
| Swap2 | 60 | PRICE_MOVING |
| ClaimFee2 | 23 | NON_PRICING |
| Swap | 18 | PRICE_MOVING |
| RemoveLiquidityByRange2 | 14 | DEPTH_MOVING |
| ClosePositionIfEmpty | 11 | NON_PRICING |
| InitializePosition | 9 | NON_PRICING |
| RebalanceLiquidity | 8 | DEPTH_MOVING |
| InitializeBinArray | 5 | NON_PRICING |
| AddLiquidity2 | 4 | DEPTH_MOVING |
| AddLiquidityByStrategy2 | 4 | DEPTH_MOVING |
| SwapExactOut2 | 2 | PRICE_MOVING |
| IncreasePositionLength | 1 | NON_PRICING |
| ClosePosition2 | 1 | DEPTH_MOVING |

Class of the transaction (first pricing-relevant family wins): swap 71, liquidity 25, fee-only 9, position-setup 6, swap and liquidity together 1.

**Pump, 373 invoking transactions** out of 700 mentions:

| Instruction | n | Effect |
|---|---:|---|
| Sell | 217 | PRICE_MOVING |
| BuyExactQuoteIn | 103 | PRICE_MOVING |
| Buy | 56 | PRICE_MOVING |
| CloseUserVolumeAccumulator | 6 | NON_PRICING |
| CollectCoinCreatorFee | 3 | NON_PRICING |
| ExtendAccount | 3 | NON_PRICING |

No `deposit`, `withdraw`, `create_pool`, `disable`, or fee-parameter update appeared.

Not observed on either program in this slice: `go_to_a_bin`, fee-parameter updates, pool initialization, `remove_all_liquidity`, limit orders, `swap_with_price_impact`.

## State reconstruction

| Needed for a quote | Available on these historical txs |
|---|---|
| DLMM LbPair, active id, fee parameters, volatility, touched bin arrays | No. `getTransaction` does not return account data. |
| Pump reserves, virtual quote, fee bps | No. Token-balance deltas are not those fields. |
| Exact `S_before` / `S_after` | **0 / 1,400**. Marked `STATE_UNAVAILABLE`. |

DLMM liquidity was not seeded from vault balances.

Because there is no authoritative curve, this census does not report `edge_before`, `edge_after`, optimal size, or lifetime. Inventing them from vault deltas would be a false edge.

## Taker join (control only)

For each sampled transaction, non-quote mints were joined to MEV.live rows with the same `two_leg_arb_mint` and `arb_slot` in `[tx_slot, tx_slot + 5]`. WSOL, USDC, and USDT were excluded so every SOL leg would not match.

This is not proof that the later arb consumed that pool, and a miss is not proof the discrepancy survived. It is a competition proxy. The `no_invoke` row is the background rate: those transactions did not run the program.

| Program | Class | n | Mint-matched within 5 slots | Elite searcher in that match |
|---|---|---:|---:|---:|
| DLMM | no_invoke (background) | 588 | 16.5% | 8.2% |
| DLMM | swap | 71 | 18.3% | 1.4% |
| DLMM | liquidity | 25 | 16.0% | 4.0% |
| DLMM | fee claim only | 9 | 0% | 0% |
| DLMM | position setup | 6 | 16.7% | 16.7% |
| DLMM | swap+liquidity | 1 | 0% | 0% |
| Pump | no_invoke (background) | 327 | 12.8% | 2.4% |
| Pump | swap | 367 | 7.9% | 0.3% |
| Pump | fee collect | 3 | 0% | 0% |
| Pump | other non-pricing | 3 | 0% | 0% |

Elite labels: Mriya, 4BQ, Dtvmxr, 7dGrdJ, gtagyE, 9EwQoN.

DLMM liquidity is not less followed than DLMM swaps, and neither is clearly above the background of transactions that never invoked DLMM. Pump swaps are not more followed than Pump non-invocations. The proxy does not support “weird mutations are neglected.” It also does not prove swaps are captured, because the same join cannot see the swaps we already know are heavily arbed. Median slot gap, where a match exists, is 0–3 slots. That is not a microsecond lifetime.

Fee-only and Pump non-swap rows are too small (n ≤ 9) to read a zero match rate as a neglected market.

## Liquidity study

25 DLMM transactions carried a depth-moving liquidity instruction (`remove_liquidity_by_range2`, `rebalance_liquidity`, `add_liquidity2`, `add_liquidity_by_strategy2`, or `close_position2`), often bundled with `claim_fee2` or `close_position_if_empty`.

The size grid (0.01 through 10 SOL, plus optimal) was not quoted. There is no bin array before and after, so `delta_edge(size)` is unknown. The economic claim “liquidity created an arb that did not exist at 0.05 SOL but exists at 0.5 SOL” is untested. The only measured fact is the taker proxy above: 16% mint-matched, against 18% for swaps and 16.5% for non-invocations.

## Multi-pool

One sampled DLMM transaction contained both a swap and a liquidity instruction. No atomic post-state was built, and routes were not re-scored. Transactions in which two pools move and a third does not were not isolated. Router transactions that touch Pump and DLMM together are inside `no_invoke` when the DEX runs only as CPI and the log line was not attributed; they were not given a combined `S'`.

## Weird state

Direct vault transfers, Token-2022 fee harvesting, and admin writes that never invoke DLMM or Pump are invisible to a program-signature census. The copied universe file has pool pubkeys and not vault pubkeys, so a vault walk was not run. No positive cycle from a non-swap vault mutation was measured. Absence of evidence here is not evidence of absence.

Inside real invocations, the non-swap mass is fee claims, empty-position closes, and position-account setup. Those do not change the quote kernel’s inputs.

## Edge lifetime

Not measured. Lifetime bins require the next account update that removes the discrepancy. Those updates were not reconstructed.

## Market size

| Quantity | This window |
|---|---|
| Total edge created by sampled state changes | Not measured (`STATE_UNAVAILABLE`) |
| Known captured arb profit (MEV.live, all routes, same 49 seconds) | 543 arbs, $40.08 |
| Uncaptured edge | Not measured |
| Long-lived uncaptured edge | Not measured |
| Pre-exec tradeable uncaptured edge | Not measured |

The $40.08 is the control population. It is not annualized, and it is not attributed to the sampled triggers.

## TRIGGER-011 unknown corpus

`/home/louis/captures/trigger011/events.jsonl` is the non-exact branch only. Exact direct swaps are counted on the hot path and are not written there. Reading the file as “the searcher saw no exact swaps” would be wrong.

| klass | Meaning | Lines |
|---|---|---:|
| 3 | ALT miss | 293,198 |
| 5 | Watched account, swap not decoded (`RELEVANT_UNKNOWN`) | 4,119 |
| 4 | Exact | not journaled on this path |

`RELEVANT_UNKNOWN` outers, by count. These program ids are not named in `programs.yaml`. Count is a discovery queue. It is not a ranking by uncaptured dollars, because those dollars were not measured.

| n | Outer program |
|---:|---|
| 1,279 | `8JjVNyj65NyhCuit2n4xAPHaMJHvJsQarg23wFrhawAc` |
| 1,123 | `3865Kzj7yiqW6A91esFu91Qxd64UY6cTbEpYRCy2KmLM` |
| 393 | `fGyU4QNAjZTHoouyzXXYWkRK4tDgcb893v3oDuVRYpj` |
| 294 | `Aet81p95mmuKjmMZPqDPmnupgU6RmQT3MmM4JojBEcst` |
| 104 | `77777nPhGvFUVAj6uq8MGyLneBt4SMwCScYZDzzztdsa` |
| 96 | `2VS1k5m7TVtjMzm5bEJcsFJYJJF4UDRyLSDqkxtuLvWh` |
| 82 | `EKMyLLujPDEQLLc7Xvx7ojc5rr5nFQPkvpoYK7bENH2` |
| 77 | `6AGp6zbGNuyZpmzeswv9KCNU15Rf37UQDqDqFAeHmS8d` |
| 55 | `EaBRrMavcvTQgGsouzkYtughZemP4QocRzBtG7ZqAFgD` |
| 40 | `8StkTM9BXnsWwWcbihCL8pUn9xBePvjQfXHqTkNjuyGD` |

`gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd` appears 21 times as an outer. That is a known searcher’s own transaction touching a watched account without a decoded direct swap, not a user trigger to copy.

In the copied 171-pool universe, index 90 is Pump pool `8R4DDi9X3RBLr876hhRJCv4Gvsy8d9SkABgb8YiHapo9` (token `J141JCiXKGcrhDCgWUTCL9qz7h943iCibNiLNfqZpump`). 2,539 of 4,119 unknown-relevant events store pool index 90. If the process reloaded a later universe, that index can point somewhere else.

Predictability of these outers is `UNKNOWN` until one of them is decoded. Prior router work (FLASHX, DF1ow, 6Vo) already showed inner swap amounts are often absent from the outer payload, which is `POSTEXEC_ONLY`.

## Uncaptured ledger

`arb-cap/alpha_census/UNCAPTURED.jsonl` has **42** rows: sampled non-swap invocations with no non-quote mint match inside 5 slots.

| Program | Class | Rows |
|---|---|---:|
| DLMM | liquidity | 21 |
| DLMM | fee claim only | 9 |
| DLMM | position setup | 5 |
| Pump | fee collect | 3 |
| Pump | other non-pricing | 3 |
| DLMM | swap+liquidity | 1 |

Every row has `actual_size_gross = null`, `edge_before = null`, `edge_after = null`, `lifetime = null`, `state_confidence = STATE_UNAVAILABLE`. There is no top 50 by dollars. Do not sum the file.

## Pre-execution

| Class | Live usability | Seen in this slice |
|---|---|---|
| Direct DLMM `swap` / `swap2`, Pump `buy` / `sell` / `buy_exact_quote_in` | `PREEXEC_EXACT` with cached reserves or bins | Dominant |
| DLMM `swap_exact_out2` | Disc not in the current parser. Amount layout not confirmed here | 2 |
| Router / unknown outer CPI | `POSTEXEC_ONLY` for the fill until a decoder shows the amount in the outer bytes | Most `RELEVANT_UNKNOWN` |
| Liquidity add / remove / rebalance / close | `PREEXEC_DETERMINISTIC_WITH_STATE` if bins and the position are cached | 25 DLMM txs |
| `go_to_a_bin`, fee-parameter writes, pool init | Same, and rare | 0 |

## Hypothesis

Obvious swaps are most of the real invocations: 71 of 112 DLMM invokes, 367 of 373 Pump invokes. The non-swap residue that can move a quote is DLMM liquidity (25 transactions). Its mint-matched follow rate matches swaps and matches transactions that never called the program. That is evidence against a neglected liquidity market in this minute, not evidence for one. Fee claims and empty-position closes do not move the quote. Fee-parameter writes, active-bin jumps, pool creation, and Pump deposit/withdraw did not occur often enough to score.

## Limitations

- One head-of-chain minute, not multiple hours. A rare admin instruction can be absent here and still exist.
- Classification uses Anchor logs. A CPI whose log line was dropped would be counted as `no_invoke`.
- The 5-slot mint join has a high background rate, so it cannot certify capture or survival.
- No bin or Pump-reserve snapshots, so no size-grid edge and no lifetime.
- No vault-account walk, so direct vault transfers were not searched.
- Multi-pool atomic `S'` was not built.
- TRIGGER-011’s journal omits exact hits, and its unknown ranking cannot be weighted by uncaptured gross.

## TOP 5 NEGLECTED TRIGGER CLASSES

These are the next classes worth an exact-state study. None has a measured uncaptured gross. “Neglected” here means “not shown to be a separate, less-competed market,” not “proven alpha.”

### 1. DLMM liquidity remove, rebalance, and add

Why it can create edge: bin amounts change `quote(size)` even when the active bin id does not. A remove can open a size that was previously inside a deep bin.

Uncaptured gross: not measured. 25 invoking transactions in 49 seconds; 21 had no mint match. The match rate (16%) equals the background (16.5%).

Lifetime: not measured.

Competition: not lower than swaps on the proxy. Elite match 4% versus 1.4% on DLMM swaps.

Pre-exec: `PREEXEC_DETERMINISTIC_WITH_STATE`. Needs the position and the touched bin arrays locally.

Production difficulty: high. The quote kernel can score it only after those accounts are in the cache, and the result still has to clear costs at a real size.

### 2. DLMM `swap_exact_out2`

Why it can create edge: it is an ordinary price-moving swap. The current instruction parser does not recognize it, so a direct exact-out can sit in `RELEVANT_UNKNOWN` with amount 0.

Uncaptured gross: not measured. 2 occurrences.

Lifetime: not measured.

Competition: unknown at n=2. It is still a swap, so the default assumption is the same competition as `swap2`, not a hidden market.

Pre-exec: likely `PREEXEC_EXACT` once the discriminator and amount layout are confirmed. Not confirmed in this pass.

Production difficulty: low relative to the others, if the layout matches `swap2`. This is a decoder gap on a known swap, not a new venue.

### 3. DLMM `go_to_a_bin`

Why it can create edge: it moves `active_id`, which the quote walks from. Liquidity already sitting at the destination bin becomes the spot.

Uncaptured gross: not measured. 0 occurrences in this slice.

Lifetime: not measured.

Competition: no sample.

Pre-exec: `PREEXEC_DETERMINISTIC_WITH_STATE`. The destination id is in the instruction; the bin liquidity has to be cached.

Production difficulty: medium once a single example is captured with bin arrays. Until one exists, there is nothing to ship.

### 4. DLMM and Pump fee-parameter updates

Why it can create edge: `update_base_fee_parameters`, `update_dynamic_fee_parameters`, `update_fee_config`, and `update_creator_fee_config` change fee inputs the kernels read. Claim and collect instructions do not.

Uncaptured gross: not measured. 0 parameter updates in this slice. The 9 DLMM fee rows and 3 Pump fee rows are claims and collects, classified NON_PRICING.

Lifetime: not measured.

Competition: no sample of parameter writes.

Pre-exec: `PREEXEC_DETERMINISTIC_WITH_STATE` when the new parameters are in the instruction data and bins or reserves are cached.

Production difficulty: medium, and only after a real parameter write is observed. Claims should stay ignored.

### 5. Pump `deposit` / `withdraw`

Why it can create edge: Pump quotes read reserves. A one-sided deposit or withdraw changes both spot and depth, and it is not a swap discriminator.

Uncaptured gross: not measured. 0 occurrences in 373 Pump invocations.

Lifetime: not measured.

Competition: no sample. Pump swaps in the same minute are the competed path (367 of 373).

Pre-exec: `PREEXEC_DETERMINISTIC_WITH_STATE` if reserves are cached and the instruction carries the token amounts.

Production difficulty: medium after the first observed deposit, low if the account layout matches the existing Pump state struct. Nothing in this window justifies wiring it.

## Decoder / research queue

Do not add these to the production trigger path on the back of this census.

1. Keep claims, empty closes, position init, and bin-array init out of the quote path. They were common and they do not move the kernel.
2. Confirm `swap_exact_out2` layout on the next live example. That is a swap decoder hole, not a new alpha class.
3. When a bin-array capture exists, score the 25-style liquidity transactions at the size grid before and after. That is the only way the liquidity hypothesis becomes a dollar result.
4. Decode the unnamed `RELEVANT_UNKNOWN` outers only if the outer bytes contain the fill. Frequency in the journal is not a profit rank.
5. A vault-account pass is a separate study. It was not done here.

ALPHA-CENSUS-001 — NO MATERIAL NOVEL ALPHA FOUND
