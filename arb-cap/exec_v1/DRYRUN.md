# Dry run

Live hour on Frankfurt, 2026-09-26 ~18:40 UTC: `would_send_new=0` `opp_synced=0`. `paper_orbit` is not running. The audit stopped at 10:22 UTC.

Full-file replay (`exec_funnel.py`, no SWQOS, `FUNDED` left 0):

- `would_send_new=71`
- `not_v1_executable=33` (3-hop)
- `ready_file_missing=38`
- `would_fire=0` while STATE-008 READY is absent

Counterfactual only, if the READY file existed: 6 rows would pass `size_gate` (four `dlmm-pump` on one pool, two `dlmm-dlmm` on a pubkey that also sits in the route0 plane). AUTH is `ready=0` `complete=0/645` `gaps=1`, so those six are not sendable.

`FUNDED=0 python arb-exec/scripts/oneshot_live.py` prints `SEND=0` and exits 0.

Hops unit tests (message, route snapshot, golden) passed on this machine. `exec_v0` was not built: no CMake here.

Phase 3 exit (a real hour with `would_fire`, a plane template, and a recorded Custom(6)) is not met. The last hour is empty, and AUTH is not coherent.
