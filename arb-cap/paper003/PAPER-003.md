# PAPER-003

`hot_decode` now applies **N**. Canonical S without a decoded trigger is fail-closed. That is the $0.61 × 377,971 class of bug.

```
RAW TRANSACTION N
        ↓
decode exact swap
        ↓
pool / direction / amount_in / min_out
        ↓
deduplicate N (signature required)
        ↓
canonical S
        ↓
predict S'
        ↓
cycle_size(S')
        ↓
opportunity_t
```

Unsupported variant → no `hot_decide`. No N → no `paper_eval_pool` on S.

## Supported

| variant | disc | amount_in | direction |
|---------|------|-----------|-----------|
| DLMM swap2 / swap | `414b3f4c…` / `f8c69e91…` | first u64 | ATA(user, token_prog, mint) vs user_token_in |
| Pump sell | `33e685a4…` | base_in | BASE_TO_QUOTE |
| Pump `buy_exact_quote_in` | `c62e1552…` | spendable_quote | QUOTE_TO_BASE |
| Pump `buy` (exact-out) | `66063d12…` | — | **fail closed** |

CPI wrappers, ALT-only pool/dir accounts, and exact-out buy do not invent N.

## Proof

### Selftest (`hot_n --selftest`)

PASS. Pump sell, `buy_exact_quote_in`, DLMM both ATA directions. Exact-out buy fail-closed.

Same transaction across incomplete / prefixed / repeated fragments:

**one tx → one `hot_seen_first` → one decide.**

### Known FEEDCAP1-derived transactions vs parsed chain

C `swapix` on raw `getTransaction` bytes vs top-level parsed ix.

**26 / 26 exact** on pool, direction, amount_in, min_out. 0 mismatches.

Both Pump directions appear (sell and `buy_exact_quote_in`). Corpus also includes txs that fail closed (CPI / exact-out / no top-level swap) — C did not invent N on those.

RPC 429 stopped the 50–100 fetch after this set. Every supported tx we compared matched. Re-run `compare_c.py` / `fetch_supported.py` when the key is cool to extend the set.

### FEEDCAP1 shred walk

`decode_feed --dir ~/captures --limit 80` finished the first cap (1,732,517 shreds). Signature required, so a pool key in a shred is not a decide. That is the structural kill of “same pair, every shred.”

Unique-count on that file is not the proof set — `msg_keys_from_prog` can still recover a message from a program-id hit the same way CORE-001 did. The 26/26 set is complete transactions.

## Recorder (tomorrow)

`syncrec` beside FEEDCAP1. RAW shreds stay the existing capture. `--sync sync.bin` on `paper_live001` (and the live binary tomorrow) writes:

| kind | contents |
|------|----------|
| 1 STATE_INIT | slot, state_version, n, pool keys |
| 2 MUTATION | before/after version, pool, N |
| 3 DECISION | sig, N, state_version used, predicted fields, opportunity_t |
| 4 EXEC | signed-ready ns, send ns, tx sig, result |

Replay tomorrow with historically correct S, not S_today.
