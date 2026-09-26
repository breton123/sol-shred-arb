# Route templates

Read from the box on 2026-09-26. Nothing was published in this pass.

## Oneshot plane

`/home/louis/arb-exec/.deploy/alt_plane.json` and `/home/louis/arb-cap/oneshot/ALT_PLANE.json`: 72 routes, 72 with uppercase `RACE_READY`, `tmpl0`, and `tmpl1`. No row has `raw > 1232`.

`alt_plane.py` sets that flag when both directions compile and the ATAs exist. It is not a Custom(6) proof.

## Hops plane

`/home/louis/arb-cap/fam6/hops_plane.json`: 1530 routes, `race_ready=0`, `vector_ready=0`.

`SIM.json` (`mode=recover`, `ok=false`) already has Custom(6) for one sample of each of `dlmm-dlmm`, `dlmm-pump`, and `pump-dlmm`. Publish never invents `race_ready`, and it does not copy the SIM proof onto the 1530 rows. It was not re-run.

## Stages not run

- `inventory` / `size` — current `SIZE.json` and `SIM.json` are the box artifacts. Not regenerated.
- `sim7` — calls `wrap_wsol(..., 50_000_000)` and `ensure_ata`. That moves SOL.
- `publish` — creates missing ATAs.
- `deploy` — program upgrade.

The exec rows that already have a oneshot template are blocked by AUTH (`ready=0`), not by a missing `tmpl0`.
