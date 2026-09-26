# Send hurdle

The send floor is **525000 lamports**. That is the fee schedule `oneshot_live.py` actually puts on the wire:

- CU limit 400000, CU price 800000 → priority plus signature = 325000
- SWQOS prepaid 150000
- safety 50000

`exec_gates.HURDLE` and `oneshot_live.HURDLE` are the same number. `size_gate` and `exec_funnel.py` both use it. A quote at or under 525000 is `below_oneshot_hurdle` and is not `would_fire`.

Paper `cap_hurdle` uses `hops_hurdle_for_seq` in `arb-core/include/hops_hurdle.h`. For `dlmm-pump` that floor is 374397 lamports, at a different CU price (1000000) and a measured CU limit. It answers a search question. It is not the send floor.

`hops_hurdle.h` was not edited. Changing it would change `would_send_new`, which the searcher writes and execution does not redefine.

3-hop and family 255 stay in the paper journal. The exec funnel tags them `not_v1_executable`. They are not a oneshot target. No hops executor was added.
