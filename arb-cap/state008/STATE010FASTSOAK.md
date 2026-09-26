# STATE-010-FASTSOAK

Validation of `S_before + exact direct swap == committed YS S` does **not** need a PAPER opportunity.

Live soak was not restarted from this ticket. Deploy the harness, then rebuild `state_apply` on Frankfurt.

## What was wrong

Shadow only ingested `opp_synced` from OrbitFlare. Sample was

`TX_EXACT ∩ PAPER opportunity ∩ coherent AUTH`

instead of

`TX_EXACT ∩ preceding AUTH`.

That is why 6 associated samples in 30 minutes.

`no_tx_shape` / 101k `TX_INCOMPLETE` was mostly **not** a missed swap join. Any pair/bin write staged a sig. Barrier only gets a shape for classified exact swaps. Liquidity and other ix timed out at slot+8 and **invalidated the pool**. That is why ~30 / 645 stayed `COHERENT`.

## Harness

```
Yellowstone tx
  → every DLMM/Pump ix classified
  → TX_EXACT? (no unknown dex discs)
  → note_tx (same TxBarrier)
  → preceding AUTH blob (last published write_dlmm / write_pump)
  → state_apply (swapix_from_flat + dlmm_apply_swap / pump_apply_swap)
  → shadow.ingest_direct
  → compare on same-sig AUTH
```

`state_apply` is the production C kernel. `apply_n.py` only packs geyser accounts + AUTH blob.

OrbitFlare / route / `opp_synced` are not required for this counter. Paper ingest still works.

## Coherence

If a staged write has **no** exact shape after 8 slots: `non_exact_reauth` — AUTH current bytes, do **not** count `STATE_TX_INCOMPLETE`.

If shape exists and writes are incomplete at the next slot: still fail-closed (`missing=…`).

## Acceptance (first exact-only funded later)

- ≥100 associated `TX_EXACT` (fastsoak + paper)
- multiple pools
- Pump **and** DLMM
- 0 unexplained prediction mismatches
- 0 publication mismatches
- `STATE_INCOMPLETE` still fail-closed on a known exact expected set

Not 4/6. Continue toward thousands while tiny controlled exec.

## Replay

`replay.py` + a jsonl of `{slot,tx,account}`. Same `apply_tx` / barrier / `state_apply`. Machine speed once captures are dumped. Optional journal is not armed on the live process.

## Build

```
cd ~/arb-core/build && cmake --build . --target state_apply
```

`STATE_APPLY` defaults to `/home/louis/arb-core/build/state_apply`.

## Counters

`tx_exact_seen` `tx_unknown_dex` `fastsoak_predict` `fastsoak_skip_no_auth` `fastsoak_skip_apply` `non_exact_reauth`
