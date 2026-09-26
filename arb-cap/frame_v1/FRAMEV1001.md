# FRAME-V1-001

Isolated from STATE-010. `state008.py` / `paper_orbit` soak was not restarted and its semantics were not changed.

## Verdict

The 590/2,464 historical-winner hole was **framing loss**, not a later decoder bug. After the SIMD-0385 parser, every winner in the hour frames. The wall that appears immediately afterward is **outer-router / inner-CPI**: 589/590 recovered v1s have no outer DLMM/Pump swap.

## Wire format (not `version <= 1`)

v1 is a different envelope from legacy/v0:

| | legacy / v0 | v1 |
|---|---|---|
| First byte | compact-u16 `nsig` | `0x81` |
| Signatures | immediately after `nsig` | tail, no length prefix |
| Accounts | compact-u16 keys; v0 + ALT | 64 inline addresses, no ALT |
| Instructions | per-ix compact-u16 | 4-byte headers, then payloads |
| Config | ComputeBudget ixs | `u32` mask + 4-byte words |
| Max size | 1232 | 4096 |

The old framer treated `0x81` as a compact-u16 / illegal version prefix and returned `FRAME_INVALID`. That is exactly how the real 2,072-byte winner `2R2ndkNhas…` was rejected.

`frame_try_at` / `frame_try_any` dispatch on `p[start] == 0x81` into `frame_parse_v1`. The legacy/v0 function is unchanged. `classify_n` is unchanged.

Fail-closed: unknown config bits, partial priority-fee mask, duplicate addresses, `>4096`, bad header → `INVALID`. Truncated across shreds → `INCOMPLETE`. Incomplete/malformed never invents a transaction.

Account/index semantics: every address is inline. Relevance is the address-array ∩ watch index. No ALT resolve, no RPC.

## Unit regression

`arb-core/tests/frame_v1.c` (Frankfurt `./build/frame_v1`):

| case | result |
|---|---|
| legacy control | FRAME |
| v0 control | FRAME (fast path + around_sig unchanged) |
| v1 complete | FRAME, `versioned=2` |
| v1 fragmented | INCOMPLETE → FRAME |
| truncated v1 | INCOMPLETE |
| unknown mask / nsig 0 / dup key / `0x82` | INVALID |
| 2072-class synthetic | FRAME |
| v1 Pump sell → trigger | IX_EXACT, watched pool, `nlut=0` |

CORE-010 and TRIGGER-011 still pass.

C framer on the real 2072-byte winner:

```
file /tmp/v1_2072.bin n=2072 rc=0 ver=2 nsig=1 nkeys=57 ninstr=1 end=2072 dex=1
```

## Historical winner recall (2464 / $2084.60)

| | before | after FRAME-V1 |
|---|---|---|
| framed | 1874 (76.06%) | **2464 (100%)** |
| invalid | 590 | 0 |
| v1 framed $ | $0 | **$349.99** |

v1 counters:

| counter | n |
|---|---|
| v1_total | 590 |
| v1_framed | 590 |
| v1_incomplete | 0 |
| v1_invalid | 0 |

All 590 v1 winners are larger than the old 1232-byte ceiling (median 1605, max 2430, 184 > 2048). That is why they exist.

Corpus: `arb-cap/frame_v1/corpus/v1/` (590 raw txs) + 8 v0 controls + `corpus.jsonl`. Refetch cache is `raw/` (gitignored). `winners.jsonl` / `recall.json` are the scoreboard.

## Downstream on recovered v1s

```
FRAME
 → inline address resolution (no ALT)
 → watched intersection
 → IX_EXACT / TX_EXACT / UNKNOWN
```

| stage | v1 (590) | all winners (2464) |
|---|---|---|
| FRAME | 590 | 2464 |
| TX_EXACT (outer DEX swap) | 1 | 4 |
| UNKNOWN | 589 | 2460 |

589/590 recovered v1s name DLMM/Pump in the address array (`dex_static=1`) but the **outer** program is a router (`AtqbPMZM…`, `5aMAKxzy…`, `King7ki4…`, `giftBX9q…`, …). The 2072-byte `$76` winner is one outer ix to `AtqbPMZMCccvHj9P8bJdg4QZuzX6bs9KAbGueL4oQcUz`. Exact N lives in the inner CPI, which this stack still refuses to invent.

So FRAME-V1 removed the format blind spot. The next coverage wall is the same TRIGGER-011/012 router problem, now visible on the fat-v1 population instead of being mixed with `FRAME_INVALID`.

## Deploy

Sources are in `~/arb-core` on Frankfurt. Tests built and run. **`paper_orbit` was not rebuilt or restarted** so the STATE-010 soak keeps its current counters. The next `paper_orbit` rebuild after that soak will pick up v1 `frame_around_sig` + overlay walk automatically.

ARBHOPS0 stays frozen until the STATE-010 bit-exact gate passes.
