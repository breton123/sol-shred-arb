# PUMP-FEE-015

Recipient-set debit from FeeConfig + GlobalConfig. No deploy. No fitted 111.

pfee (`pfeeUxB6…`) **selects the rates**. Pump AMM **dispatches** the transfers. Rates are versioned on the FeeConfig PDA `5PHirr8…` (25 SOL tiers + 25 USDC tiers + flat + exotic). Recipients and the 50% buyback carve live on GlobalConfig and can change by `update_fee_config`.

## Authoritative inputs (what AUTH should carry)

```
pump_fee_state
├─ FeeConfig (pfee PDA, program-owned, not inferred)
│   ├─ fee_tiers[i].market_cap_lamports_threshold + {lp, protocol, creator}
│   ├─ stable_fee_tiers (USDC)
│   ├─ exotic_flat_fees
│   └─ flat_fees                    # non-tier: 25 / 5 / 0 live
├─ GlobalConfig
│   ├─ lp / protocol / coin_creator bps
│   ├─ protocol_fee_recipients[8]
│   ├─ buyback_fee_recipients[8]
│   ├─ reserved_fee_recipients[7] + reserved_fee_recipient
│   ├─ buyback_basis_points         # live 5000 = 50% of protocol
│   └─ creator_fee_configurable
├─ Pool
│   ├─ coin_creator                 # LIVE tier gate (see below)
│   ├─ creator                      # documented isPumpPool PDA; too narrow
│   ├─ creator_fee_bps              # >0 overrides schedule iff configurable
│   ├─ quote_mint / base_mint
│   └─ vaults + virtual_quote
└─ base mint supply                 # for market cap
```

## Frozen formula

```
market_cap = quote_vault * base_supply // base_vault

use_tiers = (pool.coin_creator != Pubkey::default())
fees = use_tiers ? calculate_fee_tier(FeeConfig.fee_tiers, market_cap)
                 : FeeConfig.flat_fees
creator_bps = (configurable && pool.creator_fee_bps > 0)
              ? pool.creator_fee_bps
              : fees.creator_fee_bps

total = lp + protocol + creator
effective = spendable * 10000 // (10000 + total)
protocol = ceil(effective * protocol_bps / 10000)
creator  = ceil(effective * creator_bps  / 10000)
buyback  = ceil(protocol * buyback_bps / 10000)   # 50/50 live; remainder stays protocol
vault    = spendable - protocol - creator         # LP stays in the pool
```

Transfers (idx 399, sol tier 0 `2/93/30`, MC `< 420e9`):

```
126477 = vault 124940 + protocol 581 + buyback 581 + creator 375
```

`other` on the wire is the coin-creator vault ATA, not a fourth mystery rate.

## Gate (do not use isPumpPool alone)

Documented `isPumpPool` (`pool.creator == PDA(pump, ["pool-authority", base_mint])`) explains **490/1003**.

Idx 399 is **not** that PDA (`7XKqLM1…` ≠ `5QrCTJb…`) but pays **sol tier 0** bit-exact. The Pool field that partitions the 111-bps class is **`coin_creator != default`**, which selects `FeeConfig.fee_tiers`. Tier 0 is `lp=2 proto=93 creator=30` — residual vs AUTH `20/5/5` is ~111 bps. Not a constant.

| gate + fallback | vault bit-exact |
|---|---:|
| coin_creator + flat | **968 / 1003** |
| virtual ≠ 0 + flat | 926 |
| coin_creator + global | 904 |
| isPumpPool + flat | 490 |

Sells (2537) untouched. `buyback add` (fourth bps on spendable) is **0/1003** — buyback is a carve of protocol.

## Replay of the 1003

- **968** vault bit-exact under `coin_creator` + flat + published tiers
- **246** cached txs: conservation 216; vault match 236; vault+proto+buyback 118; all four amounts 106 (creator ATA labeled `other`)
- **35** still miss vault under the frozen gate. Pref-global leftover is 99, dominated by idx **216** (proto-only, `coin_creator=default`, virt=0) — that is the 013 proto-only class, not a new rate. Others (107, 102, …) sit on MC tier boundaries vs **live** mint supply; soak-time supply would be needed before calling them formula bugs.

## What pfee does

`getFees(isPumpPool, marketCap, tradeSize)` returns `{lp, protocol, creator}`. It does not move tokens. AMM CPIs SPL transfers to one protocol recipient ATA, one buyback recipient ATA, and the creator vault ATA.

## Not done (on purpose)

No kernel patch. No STATE-011. No deploy. Next: PUMP-N-015 on the 168 wrong-N rows, then association. The 35 residual buys wait on soak-time mint supply / proto-only creator=0 when `coin_creator` is default.
