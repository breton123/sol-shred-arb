# V1-ROUTER-001

PAPER / offline. STATE-010 soak was not touched. No decoder was armed. No inner CPI was invented from the packet.

## Verdict

v1 framing is solved. The 589 router winners are a concentrated CPI-research corpus.

Held-out freeze: **no shape is `symbolic_exact`**. Outer v1 fields + inline accounts often name the pool(s). They do not name `amount_in`, direction, inverse quote, or terminal state.

| counter | n |
|---|---:|
| v1_router_total | 589 |
| v1_shape_known | 502 |
| v1_symbolic_exact | **0** |
| v1_symbolic_bounded | 502 |
| v1_unknown | 87 |
| holdout | 109 |
| associated $ | 349.84 |

`symbolic_bounded` = every labeled executed pool is in the inline address array, or the address array intersects the known 528+171 pool set. That is the v1/no-ALT advantage. It is not N.

JSON meta was used only as a **label**. A rule is exact only if train and holdout are both 100% with `n_train≥4` and `n_hold≥2`. Nothing cleared that bar for input/direction/quote.

## Can outer + inline accounts + cached S determine…?

| question | result |
|---|---|
| pool(s) | **often** (502/589). Inline ∩ known pools. |
| direction | **no** as a frozen rule. Only labeled after the fact. |
| input expression | **no**. 554/589 `amount_absent_from_outer`, 35 partial, 0 full. |
| output(previous_leg) | **no** |
| balance delta | **no** from the packet (post balances are labels, not inputs) |
| inverse quote | **no** (needs pool + dir + exact in + S) |
| terminal state | **no** |

Do not implement a hot-path decoder from this. The next useful work is per-outer research on the two fat programs, not a generic “router = exact.”

## Per outer program

| N | $ | unique shapes | exact / bounded / unk | outer |
|---:|---:|---:|---|---|
| 68 | 112.29 | 68 | 0 / 56 / 12 | `AtqbPMZM…` |
| 49 | 102.34 | 30 | 0 / 44 / 5 | `King7ki4…` |
| 62 | 28.45 | 7 | 0 / 62 / 0 | `5aMAKxzy…` |
| 48 | 36.04 | 47 | 0 / 43 / 5 | `3iqgDsg6…` |
| 35 | 26.00 | 35 | 0 / 30 / 5 | `giftBX9q…` |
| 34 | 8.87 | 34 | 0 / 25 / 9 | `aUcoKkPf…` |
| 51 | 2.44 | 51 | 0 / 45 / 6 | `L6pUpkHt…` |

`AtqbPMZM` is one program, 68 distinct (disc, data_len, writable, mint) keys — not a stable template. `5aMAKxzy` is the opposite: 62 txs / 7 shapes, 39 of them `d4c338b7ba130647` / 103 B / `ws1/rs0/wu30/ru23`, all `amount_absent_from_outer`, all pool-bounded.

That 103-byte `5aMAKxzy` shape is the first Codex-research pile: pools are on the wire, N is not.

## 1232-byte receive audit

The old “tx ≤ 1232” model is valid for **what we construct and send**, not for **what we must receive**. All 589 router winners are >1232 (max 2430).

| layer | limit | action |
|---|---|---|
| `frame.c` / `TX_V1_MAX` | 4096 | already correct |
| `paper_orbit` `F_ARENA` / `g_fbuf` | 2 MiB | ok |
| `paper_orbit` `reparse_framed` | was 65535 | now `TX_RECV_MAX` 4096 |
| `txo_scan` | `uint32_t` | ok |
| `swapix_*` `uint16_t len` | 65535 | fits 4096 |
| shred / `classify_*` `uint16_t` | packet, not framed tx | ok |
| journal | sig/pool hex, not raw tx | ok |
| `FEED_N_TX_MAX` | **was 1232** | **raised to 4096** |
| `SWQOS_TX_MAX` / `V0_TX_LEN` / oneshot | 1232 | **send path — left alone** |

A FRAME-V1 pass plus a later 1232 memcpy would have been a silent drop. `FEED_N_TX_MAX` was the only receive-side hard 1232. It is not live in the STATE-010 `paper_orbit` process (that binary was not rebuilt).

`TX_RECV_MAX` is in `arb-core/include/tx.h`.

## Artifacts

- `cluster.py` / `fetch_json.py` — offline only
- `dashboard.json` / `shapes.jsonl` / `rows.jsonl`
- `txjson/` — RPC labels, gitignored

ARBHOPS0 remains frozen. The next decoder, if any, is a held-out freeze on one outer (`5aMAKxzy` 103 B first), not a 32-program allowlist.
