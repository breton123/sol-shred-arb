# DLMM-ORDERS-001

STATE-010 soak was not restarted. CORE-003 / `meteora_dlmm.c` / AUTH blob layout were not changed. `5aMAKxzy` stays research, not a production decoder.

## Verdict

The current quote/apply kernel **does not** implement

```
available_output =
    MM bin inventory
  + matching-side open limit-order inventory
  + matching-side processed_order_remaining
```

It implements **MM only**: `fill_mm` uses `swap_for_y ? amount_y : amount_x`. `dlmm.h` states the restriction: exact-in, classic SPL, **no limit orders**.

That is a correctness hole on any pool with `function_type = LimitOrder` (or Undetermined with empty reward mints) once a bin has open or processed-remaining inventory. A perfectly framed `TX_EXACT` swap is still priced wrong if S only carries X/Y.

## 1. Current kernel behavior

| question | answer |
|---|---|
| Does quote/apply include open order inventory? | **No.** `dlmm_bin_t` is `{id, amount_x, amount_y, price}`. |
| Bid vs ask distinguished? | **No.** `limit_order_ask_side` is never read. |
| Processing remaining included? | **No.** `processed_order_remaining_amount` is never read. `total_processing_order_amount` is also unread (and is **not** a fillable reserve). |
| Apply mutation | Subtracts fill from `amount_x`/`amount_y` only. A naive “add orders into max_out then still debit MM” would also corrupt MM. |

Authoritative SDK (`dlmm-sdk/commons`):

- `get_max_amount_out_with_limit_orders` = MM + open + processed remaining **on the matching side**.
- Matching side: `swap_for_y` fills **bid** (`limit_order_ask_side == 0`); `!swap_for_y` fills **ask**.
- Exact-in fill order inside a bin: **MM → processed remaining → open**.
- Gate: `LbPair.parameters.function_type` — `2` LimitOrder on; `1` LiquidityMining off; `0` Undetermined on iff every reward mint is default.

`record_dlmm.parse_bin_array` unpacks only the first 16 bytes of each 144-byte bin (`amount_x`, `amount_y`). Offsets 112–140 hold the order fields. Same hole in `snap_dlmm` / `write_dlmm` / `live.c` (id, x, y only).

`parse_lbpair` already unpacks `function_type` and **drops it** from the returned dict. `dlmm_state_t` has no `function_type`.

Offline formula + layout tests: `python test_inventory.py` (this directory).

## 2. STATE-010 dependencies

Order inventory for **swap quotes** lives on the **Bin** inside **BinArray**. It is not a missing Yellowstone account for the swap path.

| asset | subscribed today | extracted / AUTH'd | needed |
|---|---|---|---|
| LbPair | yes (`ROLE_DLMM_PAIR`) | active/vol/fee; **not** `function_type` | `function_type` (+ reward mints if type=0) |
| BinArray | yes (`ROLE_DLMM_BIN`, active-window PDAs) | **x/y only** | open, processed remaining, ask flag (and apply-side fulfilled/fees if bit-exact S') |
| LimitOrder PDA | **no** | — | not required for `available_output`; required if we ever reconstruct the book from placements rather than Bin fields |

`txexpect.DLMM_PRICING = {pair, binarray}` is the right **account** set for a swap write barrier. The hole is **field** coverage, not a missing BinArray subscription.

STATE-010 `last_s.bins = {id: (x, y)}`. A `place_limit_order` / `cancel_limit_order` that leaves MM X/Y unchanged produces an identical published S. Shadow `compare_exact` only checks touched-bin `(x, y)`. Hidden inventory can change under a coherent generation without a shadow field.

Do **not** widen AUTH / shadow / expected-write semantics while the soak is running. Next STATE generation, after soak, must publish the order fields from the same BinArray bytes already waited on.

## 3. Bit-exact validation

Invariant:

```
DLMM TX_EXACT
+ STATE_COHERENT
+ complete MM + matching-side order inventory
→ bit-exact committed state / quote
```

Codex placement/cancel scores **16/16 + 43/43** are **not in this tree**. `validate_corpus.py` is ready; `corpus/*.jsonl` is empty (`MISSING`).

Required when the corpus lands — not just account-mutation deltas:

1. Placement deltas, including bins where MM X/Y stayed unchanged and `open_order_amount` moved.
2. Cancellations (reverse of that).
3. Actual swap quotes/fills that cross those bins (kernel vs official `available_output`, then committed Bin fields).

Until then, synthetic tests already show: zero-MM + nonzero bid open ⇒ kernel `0`, official `open`; wrong-side orders must not inflate the quote.

## What not to do next

- Do not patch `fill_mm` / AUTH layout / STATE-010 mid-soak.
- Do not treat LimitOrder account absence as the blocker; BinArray already has the bytes.
- Do not invent N from v1 router topology. `5aMAKxzy` 103-byte / 39-tx shape stays a Codex research pile.

## Artifacts

- `inventory.py` — official layers, 144-byte parse, kernel MM-only contrast
- `test_inventory.py`
- `validate_corpus.py` / `corpus/`
