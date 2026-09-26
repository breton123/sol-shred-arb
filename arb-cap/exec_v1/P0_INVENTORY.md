# P0 inventory

Written 2026-09-26T18:40Z from `louis@195.242.152.178` (`festive-goldwasser`). Read-only. No send, no deploy, no SOL movement.

`paper_orbit` is not running. The audit file stopped at 2026-09-26 10:22 UTC (`PAPER-ORBIT DONE` / `NO SEND`). The last 3600s has **0** gate rows and **0** `would_send_new`.

## Processes

| Process | Status |
|---|---|
| `feed_live` | running, ~5.7h, UDP 20001, capture `/data/bsc/captures/orbitflare` |
| `state008.py` | running, ~4.9h, `FUNDED=0`, `STATE008_CAP=/data/bsc/captures/soak_pump016_20260926/state008` |
| `exec_swqos_racer` | running, ~1d, socket `/home/louis/arb-cap/oneshot/swqos.sock` |
| `paper_orbit` | **not running** (binary exists, last log ends `PAPER-ORBIT DONE`) |
| oneshot | not armed |

`ARMED` is absent. `DISARMED` says `why=closure_hops`, `funded=0`. Last `RESULT.json` is an older shot: `why=stale_custom6`, `swqos_rc=0`, confirmed, InstructionError Custom 6. `COOLDOWN.json` blocks pool prefix `dd447fcb` (`TRIGGER_MISSING` x3).

## AUTH

Live writer log (soak cap), repeating: `ready=0` `complete=0/645` `gaps=1`. The READY file is **missing** both at the default path and at the live cap:

- `/home/louis/captures/state008/READY` — missing
- `/data/bsc/captures/soak_pump016_20260926/state008/READY` — missing
- `/home/louis/captures/state007/READY` — present, 2 bytes. Retired alias. Oneshot does not arm on it.

Oneshot refuses until the live writer creates its READY file. That file is absent because the stream is not coherent, not because the path is unknown.

An older log under `/home/louis/captures/state008/state008.log` ends in `No space left on device` (10:23 UTC). Current disks are not full: `/` 391G free, `/data/bsc` 3.2T free.

## Audit file

`/home/louis/captures/paper_orbit/opp_synced.jsonl` — 166037055 bytes, age ~8.3h at inventory time. 529588 JSON rows (632 lines did not parse).

| kind | count |
|---|---|
| frame | 359257 |
| trigger011 | 42701 |
| framed_pool | 43384 |
| unknown_pool | 40797 |
| gate | 41136 |
| opp_synced | 1489 |
| opp_searchable | 816 |
| fresh_drop | 8 |

Full-file gate totals: `gross_pos=778` `cap_pos=726` `cap_hurdle=629` `mut_authoritative=163` `would_send_new=71`.

`opp_synced`: journal `race_ready=1` on 722 rows, field `tx_exact=1` on 574. The funnel's `tx_exact` column is the journal `race_ready` flag. Those two fields disagree on older rows.

Gate quotes use `cap_pos`. `opp_synced` quotes use `send_quote.cap_ok`.

`audit_nosend.py` and `audit_funnel_window.py` were run from `/tmp` (they are not installed under `arb-cap/oneshot/` on the box). The window script reports `gates_2500s=0` `would_new=0`. `audit_nosend.py` only tails 80MB, so its kind counts are a suffix, not the full file. Its `plane_keys=2` is the number of top-level JSON keys, not the route count. `agg_funnel007.py` was not run: it writes `FUNNEL.json` into the capture tree.

Last `paper_orbit` process counters (not the whole file): `opp=574` `opp_synced=574` `would_new=38` `tx_exact=1745` `ix_exact=51` `s007=1` `signed_ready=0` `NO SEND`.

## Planes

Oneshot plane (`alt_plane.json` and `ALT_PLANE.json`): **72/72** routes have uppercase `RACE_READY` plus `tmpl0` and `tmpl1`. None have `raw > 1232`. That flag in `alt_plane.py` means both directions compiled and the ATAs existed. It is not the hops Custom(6) bit.

`hops_plane.json`: 1530 routes, lowercase `race_ready=0`, `vector_ready=0` on the rows. `SIM.json` mode `recover` is `ok=false`. Three sequences recorded a real Custom(6) there (`dlmm-dlmm` cu 81777, `dlmm-pump` cu 131550, `pump-dlmm` cu 145414). Publish does not copy that proof onto the plane, and it was not re-run. `sim7` and `publish` also move SOL (wrap and ATA create). They were not run.

## Exec funnel (full file)

`arb-cap/exec_v1/exec_funnel.jsonl` (1560 rows). `auth_ready=0`. Send floor 525000.

`would_send_new=71`:

| bucket | n |
|---|---|
| not_v1_executable | 33 |
| ready_file_missing | 38 |

Families: 255 → 2, 6 → 64, 0 → 5. The 33 excluded rows are 3-hop (`dlmm-dlmm-pump`, `dlmm-dlmm-dlmm`, `dlmm-pump-dlmm`, and two pump 3-hop seqs). No family 5.

The 38 route-shaped rows all have journal `race_ready=1`. They stop on the missing STATE-008 READY file. If that file existed and the writer were actually coherent, the next bucket would be:

| next bucket | n |
|---|---|
| below_oneshot_hurdle | 19 |
| plane_miss | 13 |
| would_fire | 6 |

That `would_fire` count is a counterfactual. AUTH `ready=0`, so none of them are sendable. The six rows are four `dlmm-pump` hits on pool `e7dbf1bd…` (idx 16, cap_gross 1143411 or 1552552) and two `dlmm-dlmm` hits on `18fbce5e…` (idx 39, cap_gross 2482540). The `dlmm-dlmm` rows pass only because that pubkey is also a key in the route0 plane. The oneshot template is a DLMM↔Pump layout, not a dlmm-dlmm hops message.

`opp_synced` buckets with READY absent: `ready_file_missing=722`, `not_framed=767`. Side-by-side flags: journal `race_ready=722`, plane flag on the pool `1036`, both (AND) `269`. They are not OR'd.

## Chain (public RPC, earlier this session)

- OUR_EXEC `38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K` exists, executable, upgradeable loader, program account 36 bytes.
- Wallet `HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX` native lamports 139279919. WSOL not queried.

## Not run

`hops_live.py` `sim7` and `publish` (they wrap 50_000_000 lamports and create ATAs). `deploy`. `FUNDED=1`. `agg_funnel007.py` (it writes a capture file).
