# FLOWRA_PROBE

Standalone observe-only probe. Isolated at `arb-feed/flowra/`.
Does not touch arb-core, arb-exec, route0, SWQOS, or the shred pipeline.
No `SendBundle`. No `hot_decide`. Not wired into arb-core.

Official surface used (read before implement, 2026-09-24):

- https://docs.flowra.wtf/searchers/getting-started.md
- https://docs.flowra.wtf/searchers/orderflow-stream.md
- https://docs.flowra.wtf/searchers/api-reference.md
- https://docs.flowra.wtf/endpoints.md
- Protos: `flowrawtf/mev-protos` branch `main`
  - `searcher.proto` sha `13d1e018d84925cb0e96b0e9665ba5f74cdec2af`
  - `auth.proto` sha `da67b4db8de96821a2246bd091e525a9b3ede786`
  - `packet.proto` sha `23042a3c649b6e369e09b113e2cb168a562d7ed1`

## Product / endpoint / protocol / auth

| Item | Value |
|---|---|
| Product | Flowra Open Orderflow Auction — searcher pending stream |
| Region | Frankfurt |
| Endpoint | `https://frankfurt.mainnet.blockengine.flowra.wtf` |
| Transport | gRPC over TLS, port 443, public WebPKI |
| Proto / API | `flowrawtf/mev-protos@main` |
| RPC | `searcher.SearcherService/SubscribePendingTransactions` |
| Auth | `auth.AuthService` challenge-response. Role `SEARCHER`. Sign exact `"{pubkey}-{challenge}"` Ed25519. Access JWT as `authorization: Bearer <token>` (1 h). Refresh exists (24 h). **No secrets in this report.** |
| Filter | Official docs: empty list or `"*"` = full firehose. This 600 s run used `accounts=["*"]`. A prior 97 s connect with `accounts=[]` also received 0 batches. |
| Observe only | `GetConnectedLeaders` once for coverage. No `SendBundle`, no `SubscribeBundleResults`, no `GetTipAccounts` on the receive path. |

`T_FLOWRA_RX` = first userspace `CLOCK_MONOTONIC_RAW` (+ RDTSCP, wall UTC) taken on each packet before parse. No packets arrived, so the timestamp path was not exercised on live data.

## Runtime

Host: Frankfurt `195.242.152.178` (`festive-goldwasser`), same rack as the searcher.
`tsc_hz` = 4 193 690 244.

| Metric | Value |
|---|---|
| runtime | **600 s** |
| connection | TLS ESTAB the whole window |
| auth | ok (challenge-response) |
| messages (batches) | **0** |
| unique tx | **0** |
| duplicates | **0** |
| duplicate rate | n/a (no packets) |
| tx/s | **0.0** |
| Mbps | **0.00** |
| valid / bad | 0 / 0 |
| vote / non-vote | 0 / 0 |
| legacy / v0 / v1 | 0 / 0 / 0 |
| DLMM / Pump / DAMM / CLMM / CPMM / Orca | 0 / 0 / 0 / 0 / 0 / 0 |
| supported trigger decoded | **0** |
| capture_drop | **0** |
| work_drop | **0** |
| reconnects | **0** |
| last stream error | none (deadline stop) |
| connected leaders | **1 validator** in this region |

## Source coverage

`GetConnectedLeaders` returned **1** connected validator on the Frankfurt Block Engine.
No `packet.meta.addr` samples exist because the stream never delivered a batch.

This is consistent with a very early mainnet: the engine is reachable and our key is approved, but the pending firehose is not populated from this region tonight.

## Recorder

Append-only `FLOWRA1` + signature index, designed so tomorrow we can join by 64-byte signature:

`lead_us = T_ORBITFLARE_FIRST_ACTIONABLE - T_FLOWRA_RX`

That comparison was **not** run. There was no simultaneous premium shred feed, and Flowra delivered no signatures.

| Path | Notes |
|---|---|
| `/home/louis/captures/flowra/flowra-1790287707.flw` | 128 B header only |
| `/home/louis/captures/flowra/flowra-1790287707.idx` | empty |
| `/home/louis/captures/flowra/flowra-1790287707.meta.json` | machine report |
| `/home/louis/captures/flowra/probe.json` | same JSON on stdout |
| `/home/louis/captures/flowra/probe.console` | 1 Hz telemetry |

Disk did not block the receive path. There was nothing to record.

## Sampled eventual landing

Off-path RPC sample after the stream: **sampled 0**.

No Flowra signatures existed to poll. Landing rate, expired/not-seen, and Flowra→first-RPC time are all n/a.

RPC observation latency is **not** leader sequencing latency. That statement is unused tonight because there was no sample.

## Adapter latency

Callback → timestamp → sig extract → six-ID classify → diagnostic `hot_decode_trigger` (DLMM swap2 / Pump buy `66063d12` / Pump sell `33e685a4` only; no `hot_decide`).

**n = 0.** p50 / p90 / p99 are all 0 ns / 0 cycles. Not a measurement.

We still know the adapter compiled and the work/recorder threads ran idle. That is not a latency number for the future `N` boundary.

## Credential leakage

Checked console, JSON, and meta:

- no bearer token values
- no API keys
- no private key material
- `RUST_LOG=off`

Auth log line is only `FLOWRA auth ok (challenge-response; token not logged)`.

`.env` / `~/.flowra.env` stayed off-repo (`0600` on the server).

## What this run did prove

1. Official docs + `flowrawtf/mev-protos` are enough to speak the searcher API. Nothing was invented.
2. The approved searcher key authenticates on Frankfurt mainnet.
3. The Block Engine accepts `SubscribePendingTransactions`.
4. The control-plane connection was stable for 10 minutes (0 reconnects).
5. The isolated recorder/telemetry process is safe to leave running.

## What this run did not prove

1. That Flowra delivers pending transactions at all from FRA tonight.
2. Duplicate rate, venue mix, or trigger-decode yield.
3. That `packet.data` is a pre-sequencing Solana transaction.
4. Any lead vs OrbitFlare shreds.
5. Any on-chain landing of Flowra-seen signatures.
6. Adapter latency to the existing `N` boundary.

## Limitations

- Frankfurt currently advertises **one** connected validator. That is not a network-wide mempool.
- 600 s of authenticated subscribe produced **zero** `PendingTxNotification`s for both documented firehose forms (`[]` briefly, then `["*"]`).
- Official docs say the stream is best-effort, no replay, and a lagging subscriber is skipped. We were not lagged (`capture_drop=0`); the engine simply sent nothing.
- Relayer AOI/POI from live subscriptions is still on Flowra's own roadmap. Coverage may stay thin until more validators attach.
- Capture format is ready for a later shred join. That join was not faked.

## Verdict

Auth works. The client is isolated and observe-only. The Frankfurt pending stream did not carry a single transaction in a 10-minute window. There is nothing to classify, decode, time, or join.

**FLOWRA IS NOT READY TO BECOME AN EARLY arb-feed SOURCE**
