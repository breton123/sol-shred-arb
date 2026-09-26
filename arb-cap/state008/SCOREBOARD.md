# FASTSOAK failure reducer

root: `/data/bsc/captures/soak_fastsoak_20260925/state008`
SHADOW rows: 89938  exact={'pump': 245, 'dlmm': 8714}  mismatch={'pump': 4117, 'dlmm': 4272, 'unknown': 72590}
mismatch files: 81086  scored (pump+dlmm, skip unknown/state_missing): 8413

## PUMP
n=4118
dominant: **virtual_reserve_config 97.5%** (4015)

- reserve_mismatch: 0 (0.0%)
- vault_mismatch: 0 (0.0%)
- virtual_reserve_config: 4015 (97.5%)
- wrong_tx_association: 103 (2.5%)
- publication_ordering: 0 (0.0%)
- decode_apply_bug: 0 (0.0%)
- other: 0 (0.0%)

## DLMM
n=4295

- active_id: 69 (1.6%)
- volatility: 2239 (52.1%)
- mm_bin_xy: 0 (0.0%)
- missing_bin: 11 (0.3%)
- publication_ordering: 879 (20.5%)
- order_inventory_related: 321 (7.5%)
- wrong_tx_association: 776 (18.1%)
- other: 0 (0.0%)

## top clusters

- 4014  `pump|virtual_reserve_config|kernel_bug|reserves`
- 2204  `dlmm|volatility|fee_volatility_timing|fee_state`
- 776  `dlmm|wrong_tx_association|wrong_transaction_association|ordering`
- 589  `dlmm|publication_ordering|missing_transaction_local_write|bin_liquidity`
- 246  `dlmm|publication_ordering|missing_transaction_local_write|bin_liquidity,fee_state,volatility`
- 167  `dlmm|order_inventory_related|kernel_bug|bin_liquidity,fee_state,volatility`
- 146  `dlmm|order_inventory_related|kernel_bug|bin_liquidity,fee_state`
- 103  `pump|wrong_tx_association|wrong_transaction_association|ordering`
- 64  `dlmm|active_id|kernel_bug|active_id,bin_liquidity,fee_state,volatility`
- 30  `dlmm|volatility|fee_volatility_timing|fee_state,volatility`
- 25  `dlmm|publication_ordering|missing_transaction_local_write|bin_liquidity,volatility`
- 11  `dlmm|publication_ordering|missing_transaction_local_write|active_id,bin_liquidity,volatility`
