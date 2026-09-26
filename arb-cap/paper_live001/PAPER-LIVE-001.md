# PAPER-LIVE-001

**PnL in this file is void.** S_today (slot 450112763) was quoted against FEEDCAP1 (slots 449848541–449891196). See PAPER-002. Latency numbers below still stand.

Hours = 3.309. SOL = $115. Do not annualize. could_have_raced, not could_have_landed.
Journal records: 599595.
Universe: 102 pools, 148 routes. paced=0.

## Funnel

```
  74,688,597 shreds
        ↓
   6,908,007 relevant
        ↓
   6,908,007 complete triggers
        ↓
   1,124,965 known pool
        ↓
   1,124,965 state sufficient
        ↓
   1,124,965 affected routes evaluated
        ↓
     599,595 positive gross opportunities  (478330 sane ≤$1k; 121265 QUOTE_OVERFLOW)
        ↓
     473,273  ≥ $0.1   $762,267
        ↓
      14,000  ≥ $1   $506,540
        ↓
       1,298  ≥ $10   $457,797
        ↓
       1,297  ≥ $50   $457,786
        ↓
       1,297  ≥ $100   $457,786
```

## Searchable vs landable

| stage | Opportunities | Gross $ |
|-------|---------------|---------|
| Searcher detected | 478330 | $762,436 |
| State sufficient | 478330 | $762,436 |
| Executor exists | 432551 | $290,012 |
| Fits transaction | 432551 | $290,012 |
| Signed ready | 432551 | $290,012 |
| ≥500µs historical headroom | 62251 | $82,531 |
| ≥1ms | 61687 | $82,141 |
| ≥5ms | 59638 | $80,638 |

EXEC_FAMILY_MISSING (sane): 45779  $472,424
QUOTE_OVERFLOW (CLMM/Orca half-reserve, excluded from $): 121265
Family 0 DLMM+Pump (sane): 432551  $290,012
Families 1–4 / OTHER (sane): 45779  $472,424

Landable $ is family-0 only (v0 619 B). Overflow quotes are not money.

## could_have_raced (signed_ready only)

$$couldHaveRaced = T_{ourSigned} + T_{sendBudget} < T_{winner}$$

| Assumed signed→leader | Opportunities we were early for | Competitor realized $ |
|-----------------------|---------------------------------|------------------------|
| 50 µs | 63709 | $83,341 |
| 100 µs | 63709 | $83,341 |
| 250 µs | 62704 | $82,748 |
| 500 µs | 62251 | $82,531 |
| 1 ms | 61687 | $82,141 |
| 2 ms | 61162 | $81,663 |
| 5 ms | 59638 | $80,638 |
| 10 ms | 56748 | $76,405 |

Searchable decision-time (includes EXEC_FAMILY_MISSING):

| budget | early n | competitor $ |
|--------|---------|--------------|
| 50 µs | 69975 | $89,115 |
| 100 µs | 69975 | $89,115 |
| 250 µs | 68876 | $88,386 |
| 500 µs | 68366 | $88,118 |
| 1 ms | 67758 | $87,673 |
| 2 ms | 67180 | $87,188 |
| 5 ms | 65479 | $86,094 |
| 10 ms | 62269 | $81,666 |

Matched slots with a MEV.live winner: 400280
Winner first-shred locations: journal=journal.bin.winners.jsonl n=15283, hits fallback n=193
ourPredictedGross / competitorRealizedGross p50 = 72.70  (n=399041)
ratio p10=1.93  p90=681.94

## Our economics vs winner (best sane opp per slot, top 15 by competitor $)

| slot | our $ | them $ | ratio | our in (SOL) | them route | our fam |
|------|-------|--------|-------|--------------|------------|---------|
| 449875269 | $0.61 | $1890.74 | 0.00 | 0.822 | Raydium Concentrated Liquidity → Meteora Pools | DLMM+Pump |
| 449874802 | $0.61 | $635.49 | 0.00 | 0.822 | Raydium Concentrated Liquidity → Orca Whirlpools | DLMM+Pump |
| 449862874 | $0.61 | $444.72 | 0.00 | 0.822 | Meteora DLMM → Pump Swap | DLMM+Pump |
| 449871626 | $0.61 | $385.39 | 0.00 | 0.822 | Meteora DLMM → Pump Swap | DLMM+Pump |
| 449874881 | $0.61 | $249.94 | 0.00 | 0.822 | Meteora DLMM → Pump Swap | DLMM+Pump |
| 449849063 | $0.33 | $189.37 | 0.00 | 1.333 | Raydium CPMM → Meteora DLMM | OTHER |
| 449850496 | $0.07 | $144.57 | 0.00 | 0.100 | Meteora DLMM → Pump Swap | DLMM+Pump |
| 449855968 | $0.61 | $138.09 | 0.00 | 0.822 | Meteora DLMM → Pump Swap | DLMM+Pump |
| 449851620 | $0.61 | $134.19 | 0.00 | 0.822 | Orca Whirlpools → Meteora DLMM → Pump Swap | DLMM+Pump |
| 449849002 | $0.33 | $128.64 | 0.00 | 1.333 | Raydium CPMM → Raydium Concentrated Liquidity → Meteora DLMM | OTHER |
| 449863097 | $0.61 | $113.25 | 0.01 | 0.822 | Raydium CPMM → Orca Whirlpools → Meteora DLMM | DLMM+Pump |
| 449856538 | $0.61 | $103.58 | 0.01 | 0.822 | Meteora DLMM → Meteora DAMM V2 | DLMM+Pump |
| 449849986 | $0.33 | $103.07 | 0.00 | 1.333 | Raydium Concentrated Liquidity → Meteora DLMM → Pump Swap | OTHER |
| 449856668 | $0.61 | $101.86 | 0.01 | 0.822 | Meteora DLMM → Meteora DAMM V2 | DLMM+Pump |
| 449856076 | $0.61 | $99.79 | 0.01 | 0.822 | Meteora DLMM → Pump Swap | DLMM+Pump |

## UNCLAIMED_CANDIDATE (our +PnL, no MEV.live row in slot)

n=78050  $122,976

| slot | predicted $ | fam | hops | signed | next-state µs |
|------|-------------|-----|------|--------|---------------|
| 449849247 | $352.96 | OTHER | 3 | 0 | 421 |
| 449849247 | $352.96 | OTHER | 3 | 0 | 375953 |
| 449849280 | $352.96 | OTHER | 3 | 0 | 6851908 |
| 449849305 | $352.96 | OTHER | 3 | 0 | 10017 |
| 449849305 | $352.96 | OTHER | 3 | 0 | 226508 |
| 449849351 | $352.96 | OTHER | 3 | 0 | 674416 |
| 449849471 | $352.96 | OTHER | 3 | 0 | 1143288 |
| 449849622 | $352.96 | OTHER | 3 | 0 | 85521201 |
| 449849944 | $352.96 | OTHER | 3 | 0 | 8126 |
| 449849944 | $352.96 | OTHER | 3 | 0 | 23363 |
| 449849944 | $352.96 | OTHER | 3 | 0 | 1618 |
| 449849944 | $352.96 | OTHER | 3 | 0 | 1361626 |
| 449849949 | $352.96 | OTHER | 3 | 0 | 354492 |
| 449849967 | $352.96 | OTHER | 3 | 0 | 17736445 |
| 449850122 | $352.96 | OTHER | 3 | 0 | 14606531 |
| 449850178 | $352.96 | OTHER | 3 | 0 | 31268512 |
| 449850336 | $352.96 | OTHER | 3 | 0 | 915820 |
| 449850571 | $352.96 | OTHER | 3 | 0 | 3046034 |
| 449851067 | $352.96 | OTHER | 3 | 0 | 5600317 |
| 449851189 | $352.96 | OTHER | 3 | 0 | 1316621 |

## Machine (replay)

- actionable→decision n=1048576 p50=28170 p99=141613 p999=148272 ns
- actionable→signed   n=432552 p50=63911 p99=70901 p999=74306 ns
- burst_max in 1 ms: 44
- signer_busy: 0  stale: 0
- winner sigs seen: 23694 / 171277
- opportunities/sec (window): 181201.3 /hr-window  (599595 / 3.309 h)
