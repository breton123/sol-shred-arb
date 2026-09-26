# Pre-arm checklist

**Shot not taken.** `FUNDED` was not set to 1. The racer was not opened. No SOL was moved.

Arm only after a human says so in that request, and only after every line below is true on the Frankfurt box.

1. Wallet native balance covers `MAX_IN` (50000000) plus fees, and the WSOL wrap of `MAX_IN` has landed. Oneshot refuses when native is short. At inventory time the public native balance was 139279919 lamports. WSOL was not queried. That is not an arm decision.
2. OUR_EXEC `38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K` exists, is executable, and is owned by the upgradeable loader. Do not upgrade it while a oneshot is armed. Never BPF Loader 2.
3. Plane snapshot: the route's `alt_plane.json` row has uppercase `RACE_READY`, `tmpl0`, and `tmpl1`, and that pool pubkey is not shared by a second DLMM/Pump pair. Lowercase hops `race_ready` does not count. The plane flag is not a Custom(6) proof. The pool must also be `RACE_READY` in `template_audit.json` from the read-only audit. Do not set the flag by hand.
4. The live `STATE008_CAP` READY file exists because `state008.py` is coherent (`ready=1`). On 2026-09-26 the soak cap had no READY file (`ready=0`, `complete=0/645`, `gaps=1`). `state007/READY` was present and does not arm.
5. `exec_swqos_racer` is listening on `/home/louis/arb-cap/oneshot/swqos.sock`.
6. `exec_funnel.py` on the same hour shows `would_fire` for `dlmm-pump` or `pump-dlmm` only. Family 6 (`dlmm-dlmm`) and 3-hop are not oneshot shapes. The row must have `tx_exact=1` and `plane_race_ready=1`. Those flags are AND, not OR. The pool must be one of the unsigned-sim `RACE_READY` routes in `EXEC_READY_REPORT.md`.
7. `cap_gross` is above 525000. That is the send floor.
8. `COOLDOWN.json` does not have `SEND_BLOCKED` on that pool.
9. `ARMED` does not already exist.

Abort if any line fails. One attempt, then `DISARMED`. No retry and no fee ladder. After `RESULT.json`, set `FUNDED=0` and explain the wallet delta from `why` and `race`.

This file is the checklist only. It is not approval to send.
