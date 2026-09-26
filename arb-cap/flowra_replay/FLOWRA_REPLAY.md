# FLOWRA_REPLAY

Offline replay of the overnight Frankfurt capture. Isolated in `arb-feed/flowra/`.
Does not modify arb-core / arb-exec / shred / SWQOS. Does not call `hot_decide`.
Does **not** quote `liveuniv` S_today as money (PAPER-002 chronology trap).

Capture: `/home/louis/captures/flowra/flowra-1790294871.flw` (still open under the 12 h probe; last rec may be truncated).

Universe membership only: `arb-cap/live002/liveuniv.json` (102 pools, slot 450112763). That slot is **not** the capture clock. Used solely as “is this pool one we trade.”

## Adapter (race handoff)

Common N event for Flowra and OrbitFlare:

- C: `arb-feed/include/flowra_n.h` (`feed_n_t`, `feed_race_t`)
- Rust: `arb-feed/flowra/src/n.rs` (`FeedN`, `RaceTable`)

Rules:

- `T_RX` is taken before parse.
- Dedup by 64-byte signature. First timestamp wins.
- `lead_ns = T_ORBITFLARE_FIRST_ACTIONABLE - T_FLOWRA_RX` when both sources see the same sig.
- Negative `lead_ns` means Flowra was first (the pre-sequencing case we care about).
- `have_n` means a supported `hot_decode_trigger` variant recovered `pool / direction / amount_in / min_out`.
- A later live loop can call `hot_decide` on that N. This replay does not.

OrbitFlare is not wired yet. The table is ready: OF emits `FEED_SRC_ORBITFLARE` with the same `feed_n_t`.

## Local funnel (no RPC)

| stage | n |
|---|---|
| records (until truncate) | 126,744 |
| first-seen | 96,942 |
| dup records | 29,802 |
| valid Solana tx | 96,941 |
| bad | 1 |
| vote / non-vote | 6,134 / 90,807 |
| DLMM / Pump / DAMM / CLMM / CPMM / Orca | 1,113 / 9,681 / 1,148 / 1,609 / 667 / 2,489 |
| same pending tx touches DLMM **and** Pump | 206 |
| supported trigger decode | **5,417** |
| decode pool ∈ liveuniv | **103** |

103 is the actable set for route0-shaped work: we recovered N **and** the pool is in today’s universe. That is not an opportunity and not a dollar.

Top known pools (count of decoded N): `8VHKSU5…` 38, `6e3jZL…` 19, `B1zosT…` 17.

## Did they land? Did anyone take them?

Off-path RPC on **all 5,417** supported-trigger signatures. RPC first-seen is **not** leader sequencing latency.

| | |
|---|---|
| trigger sampled | 5,417 |
| eventually landed | **4,026 (74.3%)** |
| failed on-chain | 547 |
| expired / never seen | 844 |
| known-pool triggers | 103 |
| known-pool landed | **18** |
| those 18 were same-tx DLMM+Pump | 0 |
| sibling slots scanned | 15 |
| slots with ≥2 DLMM+Pump txs | 0 |

So: the overnight firehose is **real subsequently-landed pending transactions**, not noise. Most supported swaps land. Almost none of the **known-universe** N’s landed (18/103) — either they expired, failed, or the pool-index heuristic missed the real pool.

We did **not** find a clean “searcher backran this known trigger in the same slot” sample in the 15 blocks pulled. The 206 same-tx DLMM+Pump pending txs are a better place to look next (those look like already-packed arbs, not user triggers).

No `$` from this replay. No `could_have_raced`. No S_today quote.

## What this enables

1. FLOWRA1 is replayable and joinable by sig.
2. `feed_n_t` is the race boundary: Flowra now, OrbitFlare when shreds are simultaneous.
3. If Flowra’s `T_RX` is before shred first-actionable, the first-wins table keeps the early N and a later `hot_decide` can run on it without waiting for OF.

## Not done

- OrbitFlare not emitting `feed_n_t` yet
- Live `hot_decide` not connected
- Historical S / `S_PRETOKEN` quotes on the 18 landed known-pool txs
- Full getBlock scan of the 206 dual-venue pending sigs

**FLOWRA IS A REAL PENDING FEED (74% of decoded triggers land). IT IS NOT YET WIRED TO DECIDE. THE RACE ADAPTER IS THE HANDOFF.**
