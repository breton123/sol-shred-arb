# TIMER-DECAY-001 — prospective fee-decay shadow

Read-only consumer of live STATE-010 (`/dev/shm/arb_auth009`). `state008.py` and `paper_orbit` were not restarted or edited. No sends.

Window: **720 s** starting unix **1790376614** (slot ~450490946). Universe 645 pools. Quotes are the existing DLMM/Pump kernels with `now_ts` set to the scheduled boundary. Hurdle is `hops_hurdle_for_seq` (`dlmm-pump` 374 397 lamports, `pump-dlmm` 384 440). Sizes: 0.05 / 0.10 / 0.25 / 0.50 / 1 / 2 / 5 SOL. Only typed SOL-quoted DLMM↔Pump 2-hops sharing the pool token.

## Headline

| | |
|---|---:|
| Scheduled decay boundaries | 1 460 |
| Fired (boundary reached in-window) | 807 (519 filter, 288 decay) |
| Survived with no DLMM write | 154 (19.1% of fired) |
| Partner Pump also untouched | 127 |
| Survived and fee rate actually fell | 145 |
| Routes crossing `net <= 0` → `net > 0` | **2** |
| Theoretical net opened (best size each) | 1 663 251 lamports (**0.00166 SOL**) |
| Known searcher capture | 0 |
| Naturally closed by later write | 1 |
| Still open at end of soak | 1 |
| Account event at the crossing | **0 / 2** |

The fee-decay rule is economically real. In this 12 minutes it opened **two** post-hurdle cycles, both on the `filter` boundary (volatility reference halved), both with **no account write** an event-driven searcher would have received. The opened net is **0.00166 SOL**. That is not a book.

## Mechanism check (live, not the 840/840 offline proof)

On every survived boundary the quote kernel ran `update_references` then `update_volatility` at `now_ts = last_upd + {filter,decay}_period`.

Of 154 untouched DLMM states, 145 dropped `total_fee_rate`. Median drop among survivors: −14 291 (fee-precision units). None rose. The 9 zeros are already-flat variable fee (decay after vol is already ~0).

Typical live parameters in this universe: `filter_period` 30 or 300 s, `decay_period` 600 or 1 200 s, `reduction_factor` 5 000.

## The two TIMER_DECAY_OPEN rows

### 1. `GiRNCYDd…` / token `5NhN6zzD…pump` — filter

- Scheduled at 1790376615, boundary 1790376623 (8 s later). Slot at schedule 450490946.
- DLMM gen 5973 unchanged. Partner Pump `3yXXas5wQqC6LzV9x22GEqVr9Dgg1VC6yynkVGhRWJWM` gen unchanged.
- Fee 66 004 964 → 54 001 132 (`vol_acc` 73 041 → 36 520).
- Route `pump-dlmm`.
- 0.10 SOL: net −1 283 915 → **+229 826**
- 0.25 SOL: net −2 769 595 → **+1 012 676** (best)
- 0.05 / 0.50 / 1 / 2 / 5: no crossing recorded.
- `event_at_cross = false`.
- Next DLMM write 51 s later (slot 450492160). No MEV.live row on that mint in the 30 s after the boundary. Class: **NATURALLY_CLOSED_BY_FLOW**. No known searcher.

### 2. `2gXV31km…` / token `CTPoyCwk…pump` — filter

- Scheduled 1790377179, boundary 1790377209 (30 s). Slot 450494065.
- Partner Pump `3dcwhqJp6JBTJPq8ga335HWgSQVS7uQmdmeX7iGjMNpj` untouched.
- Fee 4 108 914 → 2 527 229 (`vol_acc` 162 362 → 81 181).
- Route `pump-dlmm`.
- 0.25 SOL: net −76 639 → **+320 902** (gross was already +307 801, below hurdle)
- 0.50 SOL: net −161 724 → **+650 575** (best)
- 1 SOL: net −1 139 208 → **+536 018**
- 0.05 / 0.10 / 2 / 5: no crossing.
- `event_at_cross = false`.
- Still open at soak end, **125 s**, no MEV.live taker. Class: **STILL_OPEN**.

Both openings needed sizes **above 0.05 SOL**. The 0.05 clip the paper path uses would have reported nothing.

## Counterfactual

At both crossings the AUTH ring still held the same DLMM generation and the same partner Pump generation as at schedule. There was no Yellowstone account event, no swap, no liquidity write. An event-driven searcher watching those accounts would have been silent. That is a **non-event trigger**.

## Capture vs invalidate

| Opening | Lifetime | Subsequent taker | Known searcher |
|---|---:|---|---|
| GiRNCYDd filter 0.25 | 51 s | none (later pool write) | no |
| 2gXV31km filter 0.50 | ≥125 s | none at soak end | no |

Lifetimes are two samples. Do not treat 51 s as a p90.

## What did not happen

- No `decay` (vol → 0) crossing in 12 minutes. 19 decay boundaries survived; fee moved; none crossed the hurdle on a quoted size.
- 28 survived boundaries had some size with `net > 0` after the timer. 26 of those were already `net > 0` before, or failed the `<= 0 → > 0` test. Only the two rows above are TIMER_DECAY_OPEN.
- 653 of 807 fired boundaries were hit by a later DLMM write before the clock. Those are ordinary flow, not timer alpha.
- 3-hop / DLMM-DLMM routes were not scored.

## Limitations

- Python port of `meteora_dlmm.c` / `pump.c` / `cycle.c`, not a link of the frozen objects. Fee-reference update matches the 840/840 rule. A bit-exact C replay of the two openings was not run.
- `now_ts` is unix wall time, same unit as on-chain `last_update_timestamp` and the same clock STATE-010 stamps into the blob.
- MEV.live is a 30 s mint join after the boundary. A miss is not proof no arb landed; it is consistent with no labeled taker.
- 12 minutes. Do not annualize 0.00166 SOL.
- STATE-010 publication lag is not subtracted. If AUTH is late, we schedule from a slightly stale `last_upd`. Survived-to-boundary still means no newer AUTH gen.

## Files

- `arb-cap/timer_decay/SUMMARY.json`
- `arb-cap/timer_decay/TIMER_DECAY_OPEN.jsonl`
- `arb-cap/timer_decay/LEDGER.jsonl`
- Server soak: `/home/louis/research/timer_decay/`

## Verdict

The timer is a real, non-event trigger. In this soak it is **not** a material book: two openings, 0.00166 SOL theoretical net, no searcher, sizes the 0.05 cap would miss.

Do not wire a production timer from this file. If a later soak over hours still shows ~0.001 SOL / 12 min and no fat tail, the class stays a curiosity. If a later soak shows a 0.5–2 SOL net that lives tens of milliseconds with no account event, that is the production ticket.
