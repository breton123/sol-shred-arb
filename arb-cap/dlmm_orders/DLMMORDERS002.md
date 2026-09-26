# DLMM-ORDERS-002

Offline STATE-011 / order-aware kernel contract. STATE-010 soak was not restarted. `fill_mm` in `meteora_dlmm.c` was not edited. AUTH v1 blob / `write_dlmm` / `live.c` were not changed.

## Goal

Land later as **one** generation after soak:

```
BinArray raw bytes
      ↓  parse MM x/y + processed remaining + open + ask flag
LbPair raw bytes
      ↓  function_type + reward-mint default mask
AUTH SHM (richer S)
      ↓
fill_bin → fill_mm / fill_processed_order / fill_open_orders
```

Barrier accounts stay `{LbPair, BinArray}`. No new subscriptions.

## Representation (on-chain, not a bid/ask pair)

A Bin stores **one** `open_order_amount` and `limit_order_ask_side`. Side is a gate, not two live books.

```
dlmm_o_bin_t
  id
  amount_x, amount_y                          MM
  processed_order_remaining_amount            fillable processing layer
  open_order_amount                           fillable open layer
  total_processing_order_amount               bookkeeping; not a reserve
  order_age
  limit_order_ask_side                        0 bid / !=0 ask
  price

dlmm_o_state_t
  function_type                               0 undetermined, 1 LM, 2 limit-order
  reward_mint_live_mask                       bit i ⇒ reward_infos[i].mint != 0
  …existing pair / window fields
```

Orders enabled iff SDK `is_support_limit_order`: type 2; type 1 off; type 0 only if mask==0.

## Fill split and S'

```
fill_bin()
├─ fill_mm()                  max_out = amount_y or amount_x
├─ fill_processed_order()     matching side only
└─ fill_open_orders()         matching side only
```

20 MM + 10 processed + 30 open is **not** `amount_y -= 60`.

```
amount_y                         -= 20
processed_order_remaining_amount -= 10
open_order_amount                -= 30
amount_x                         += 20     # MM input only (Q1 / excluded)
```

Vault reserves still see the full take. Order takes never debit MM.

Not mutated yet (public SDK quote path does not apply them): `fulfilled_order_amount_*`, `limit_order_fee_*`, `split_fee` LO share. Inventory layers + quote are the bit-exact surface for this ticket.

## Fixtures (quote **and** post-bin)

`python test_fill_bin.py` — MM sufficient; MM→processed; processed→open; all three; wrong-side ignored; `function_type` LM off; type 0 ± reward mint; two bins with orders; fake max_out patch would poison S'.

C twin: `dlmm_orders002` (not in `core`). Linux-only tree. Price must be set (no link to `meteora_dlmm.c`).

`test_state011_draft.py` — placement-shaped snap: MM x/y unchanged, `open` moves.

## Trigger family (after kernel is live)

`LIMIT_ORDER_PLACE` / `CANCEL` / `PROCESS` can change executable depth with MM X/Y flat. Current searcher sees “nothing economically changed.”

## Landing (STATE-011, after soak)

1. Publish `function_type`, reward mask, per-bin open / proc_rem / ask in AUTH.
2. Switch shadow compare to those fields.
3. Link `dlmm_orders` apply into paper/hot in the same generation as the blob.
4. Then attach Codex 16/16 + 43/43 + swap fills.

Do not ship half of this against v1 S.

## Artifacts

- `arb-core/include/dlmm_orders.h`
- `arb-core/src/dex/dlmm_orders.c`
- `arb-core/tests/dlmm_orders002.c`
- `fill_bin.py` / `state011_draft.py` / `wire.py`
