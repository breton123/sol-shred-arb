Drop Codex fixtures here. Not in git until they exist.

- `placements.jsonl` — target 16/16 known placement deltas
- `cancellations.jsonl`
- `swaps.jsonl` — TX_EXACT quotes/fills on bins that have order inventory

A placement that only moves `open_order_amount` (MM `amount_x`/`amount_y` unchanged) is the interesting case: current AUTH S is identical before and after.
