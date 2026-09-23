# arb-cap

Ugly recorder. Not arb-core.

```bash
export HELIUS_API_KEY=...
python3 record_dlmm.py 180 triples.jsonl
# on Frankfurt:
./json_to_cap ~/arb-core/data/dlmm.cap < triples.jsonl
~/arb-core/build/core004 --cap ~/arb-core/data/dlmm.cap
```

A triple is emitted only when exactly one successful DLMM `swap`/`swap2` lands between two account snapshots. Multiple swaps in the window are discarded (alignment). Missing bin is a coverage observation, not a math fail.

`reserve_*` in the record is the sum of cached bins (what `dlmm_apply_swap` mutates), not vault token-account balances.
