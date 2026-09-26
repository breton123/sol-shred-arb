# STATE-003

Seeing N early is for deciding. Authoritative execution is for canonical S.

```
observe  → S' → opportunity_t     never writes S
confirm  → hot_commit             only after N landed
reject   → discard speculation    S unchanged
refresh  → account snapshot       → SYNCED
```

Only `SYNCED` pools are sendable. Mismatch → `STALE` → send disabled → refresh.

Frozen ±16 kernel is unchanged. Walk distance is measured on a fat control-plane dump.

`paper_orbit` no longer `hot_commit`s shred-seen N.

Walk on authoritative ±128 dumps of the 101 DLMM N from the paper session:

`n_ok=95 n_fail=6  p50=3 p90=7 p99=8 p99.9=8 max=9`

±16 was enough for this corpus **if S is synced**. The 72 missing-bin hits were poisoned `window_center` after committing failed N, not a 71-bin walk. Kernel K stays 16. Widen only after a larger live sample.

`mwSC5UAu`: residual vs vault is not a kernel bug. See STATE-004 — vault equations are exact; `reserve_*` is priced liquidity; the −21121 “chain” active_id was a later pair read (event is −21127→−21129). SEND BLOCKED until price state matches.
