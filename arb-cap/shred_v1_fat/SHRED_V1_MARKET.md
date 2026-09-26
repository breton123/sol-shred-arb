# SHRED_V1_MARKET

3h18m premium shred window. Successful MEV.live arbs only.
Headroom = T(searcher first) - T(N actionable). No local budget subtracted.
Located both sides: 212 / 225 pairs. Hours = 3.309.
Do not annualize. $/hr is this window only.

## Headlines

| | $ | $/hr |
|---|---:|---:|
| TOTAL SUCCESSFUL ARB | $10,995 | $3,322/hr |
| SHRED-COMPETABLE (headroom ≥ 500 µs, all routes) | $1,697 | $513/hr |
| CURRENT UNIVERSE (DLMM+Pump, ≥ 500 µs) | $807 | $244/hr |
| EXPANDED (DLMM/Pump/DAMM/CLMM/CPMM/Orca, ≥ 500 µs) | $1,582 | $478/hr |

## Sensitivity — captured competitor $ with enough headroom

| budget | all routes | route0 DLMM+Pump | expanded |
|---:|---:|---:|---:|
| 20 µs | $2,248 | $1,001 | $2,133 |
| 50 µs | $2,248 | $1,001 | $2,133 |
| 100 µs | $2,248 | $1,001 | $2,133 |
| 250 µs | $1,791 | $818 | $1,675 |
| 500 µs | $1,697 | $807 | $1,582 |
| 1 ms | $1,445 | $795 | $1,330 |
| 2 ms | $1,357 | $782 | $1,242 |
| 5 ms | $1,151 | $747 | $1,134 |
| 10 ms | $528 | $196 | $528 |

## Sensitivity × universe

| universe | 50µs | 100µs | 250µs | 500µs | 1ms | 5ms |
|---|---:|---:|---:|---:|---:|---:|
| all routes | $2,248 | $2,248 | $1,791 | $1,697 | $1,445 | $1,151 |
| route0 | $1,001 | $1,001 | $818 | $807 | $795 | $747 |
| expanded | $2,133 | $2,133 | $1,675 | $1,582 | $1,330 | $1,134 |

## Dollars by route family

| route | n | all $ | 100µs | 250µs | 500µs | 1ms | 5ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| DLMM -> Pump | 87 | $3,773 | $913 | $818 | $807 | $795 | $747 |
| CLMM -> Meteora Pools | 1 | $1,891 | $0 | $0 | $0 | $0 | $0 |
| CPMM -> DLMM | 16 | $789 | $114 | $78 | $78 | $78 | $10 |
| CLMM -> Orca | 3 | $660 | $12 | $12 | $12 | $12 | $12 |
| CLMM -> DLMM -> Pump | 17 | $607 | $210 | $185 | $101 | $101 | $81 |
| Orca -> DLMM | 7 | $371 | $292 | $92 | $92 | $0 | $0 |
| DLMM -> DAMM | 7 | $279 | $136 | $136 | $136 | $35 | $35 |
| CPMM -> CLMM -> DLMM | 7 | $266 | $143 | $143 | $143 | $143 | $143 |
| DLMM | 8 | $246 | $88 | $0 | $0 | $0 | $0 |
| CPMM -> Orca -> DLMM | 8 | $223 | $11 | $0 | $0 | $0 | $0 |
| CLMM -> DLMM | 8 | $160 | $80 | $80 | $80 | $63 | $38 |
| Orca -> DLMM -> Pump | 2 | $147 | $0 | $0 | $0 | $0 | $0 |
| CLMM | 3 | $137 | $54 | $54 | $54 | $54 | $54 |
| Pump -> DAMM | 2 | $79 | $22 | $22 | $22 | $22 | $0 |
| Orca -> Meteora Pools | 1 | $77 | $0 | $0 | $0 | $0 | $0 |
| CLMM -> Pump | 3 | $60 | $0 | $0 | $0 | $0 | $0 |
| DLMM -> Pump -> DAMM | 3 | $53 | $29 | $29 | $29 | $0 | $0 |
| CPMM -> DLMM -> Pancake | 1 | $49 | $0 | $0 | $0 | $0 | $0 |
| RayV4 -> CPMM -> Orca -> DLMM | 1 | $48 | $48 | $48 | $48 | $48 | $0 |
| CPMM -> CLMM -> Orca -> DLMM | 3 | $44 | $0 | $0 | $0 | $0 | $0 |
| CPMM -> DLMM -> Manifest | 3 | $42 | $16 | $16 | $16 | $16 | $0 |
| RayV4 -> DLMM -> Pump | 1 | $39 | $0 | $0 | $0 | $0 | $0 |
| CPMM -> CLMM -> DAMM -> Tessera V | 1 | $39 | $0 | $0 | $0 | $0 | $0 |
| DLMM -> Manifest | 1 | $29 | $0 | $0 | $0 | $0 | $0 |
| CLMM -> Orca -> DLMM | 2 | $28 | $14 | $14 | $14 | $14 | $14 |

## Protocol addition ROI (marginal capturable $ at ≥ 500 µs)

| add | extra $ | extra $/hr | cumulative |
|---|---:|---:|---:|
| A  DLMM+Pump | $807 | $244/hr | $807 |
| B  +DAMM v2 | $188 | $57/hr | $995 |
| C  +Ray CLMM | $248 | $75/hr | $1,243 |
| D  +Ray CPMM | $221 | $67/hr | $1,463 |
| E  +Orca | $118 | $36/hr | $1,582 |

## Competition

| competitors | opportunities | $ extracted | median first $ | p90 | max |
|---|---:|---:|---:|---:|---:|
| 1 | 204 | $10,389 | 22.20 | 85.89 | 635.5 |
| 2 | 0 | $0 | — | — | 0.0 |
| 3-5 | 0 | $0 | — | — | 0.0 |
| 6-10 | 0 | $0 | — | — | 0.0 |
| 10+ | 0 | $0 | — | — | 0.0 |

## Elite absent (winner headroom ≥ 500 µs)

| exclusion | opps | winner $ | all extracted $ |
|---|---:|---:|---:|
| any | 37 | $1,650 | $1,650 |
| no Mriya | 29 | $1,149 | $1,149 |
| no Mriya/4BQ | 29 | $1,149 | $1,149 |
| no Mriya/4BQ/Dtvmxr | 20 | $837 | $837 |

## Jackpot  profit≥$50 ∧ competitors≤3

### ≥ 500 µs  n=8  winner $=1050

| profit | headroom | n | route | winner | Mriya | 4BQ | tick | leader |
|---:|---:|---:|---|---|---|---|---:|---|
| 385.4 | 5.87 ms | 1 | DLMM -> Pump | Mriya | Y |  | 9 | Bitwise Onchain Solutions |
| 138.1 | 6.51 ms | 1 | DLMM -> Pump | gtagyESa |  |  | 30 | HZKop...BSpEc |
| 128.6 | 12.68 ms | 1 | CPMM -> CLMM -> DLMM | CatyeC3L |  |  | 47 | Bitwise Onchain Solutions | Jito BAM |
| 101.9 | 0.62 ms | 1 | DLMM -> DAMM | Dtvmxr |  |  | 13 | HZKop...BSpEc |
| 91.7 | 0.61 ms | 1 | Orca -> DLMM | 7dGrdJRY |  |  | 57 | Stardust Staking - 0% fee forever + MEV 0% fee |
| 85.9 | 27.41 ms | 1 | DLMM -> Pump | Dtvmxr |  |  | 16 | oixpq...vxMZE |
| 65.1 | 22.46 ms | 1 | DLMM -> Pump | CatyeC3L |  |  | 46 | Next Finance Tech |
| 53.7 | 40.96 ms | 1 | CLMM | 888enCW7 |  |  | 34 | Kraken 2 |

### ≥ 1 ms  n=6  winner $=857

| profit | headroom | n | route | winner | Mriya | 4BQ | tick | leader |
|---:|---:|---:|---|---|---|---|---:|---|
| 385.4 | 5.87 ms | 1 | DLMM -> Pump | Mriya | Y |  | 9 | Bitwise Onchain Solutions |
| 138.1 | 6.51 ms | 1 | DLMM -> Pump | gtagyESa |  |  | 30 | HZKop...BSpEc |
| 128.6 | 12.68 ms | 1 | CPMM -> CLMM -> DLMM | CatyeC3L |  |  | 47 | Bitwise Onchain Solutions | Jito BAM |
| 85.9 | 27.41 ms | 1 | DLMM -> Pump | Dtvmxr |  |  | 16 | oixpq...vxMZE |
| 65.1 | 22.46 ms | 1 | DLMM -> Pump | CatyeC3L |  |  | 46 | Next Finance Tech |
| 53.7 | 40.96 ms | 1 | CLMM | 888enCW7 |  |  | 34 | Kraken 2 |

### ≥ 5 ms  n=6  winner $=857

| profit | headroom | n | route | winner | Mriya | 4BQ | tick | leader |
|---:|---:|---:|---|---|---|---|---:|---|
| 385.4 | 5.87 ms | 1 | DLMM -> Pump | Mriya | Y |  | 9 | Bitwise Onchain Solutions |
| 138.1 | 6.51 ms | 1 | DLMM -> Pump | gtagyESa |  |  | 30 | HZKop...BSpEc |
| 128.6 | 12.68 ms | 1 | CPMM -> CLMM -> DLMM | CatyeC3L |  |  | 47 | Bitwise Onchain Solutions | Jito BAM |
| 85.9 | 27.41 ms | 1 | DLMM -> Pump | Dtvmxr |  |  | 16 | oixpq...vxMZE |
| 65.1 | 22.46 ms | 1 | DLMM -> Pump | CatyeC3L |  |  | 46 | Next Finance Tech |
| 53.7 | 40.96 ms | 1 | CLMM | 888enCW7 |  |  | 34 | Kraken 2 |

## Fat tail (winner ≥ $10, located)

| ≥$ | n | $ | ≥500µs n | ≥500µs $ |
|---:|---:|---:|---:|---:|
| 10 | 212 | $10,389 | 39 | $1,697 |
| 25 | 84 | $8,379 | 15 | $1,307 |
| 50 | 41 | $6,904 | 8 | $1,050 |
| 100 | 14 | $4,983 | 4 | $754 |
| 250 | 4 | $3,356 | 1 | $385 |
| 500 | 2 | $2,526 | 0 | $0 |
| 1000 | 1 | $1,891 | 0 | $0 |

## Top scored  profit × headroom / competitors

| score | profit | headroom | n | route | winner | elite |
|---:|---:|---:|---:|---|---|---|
| 2,353,777 | 85.9 | 27.41 ms | 1 | DLMM -> Pump | Dtvmxr | Dtvm |
| 2,262,092 | 385.4 | 5.87 ms | 1 | DLMM -> Pump | Mriya | Mriya |
| 2,198,346 | 53.7 | 40.96 ms | 1 | CLMM | 888enCW7 |  |
| 1,631,153 | 128.6 | 12.68 ms | 1 | CPMM -> CLMM -> DLMM | CatyeC3L |  |
| 1,462,920 | 65.1 | 22.46 ms | 1 | DLMM -> Pump | CatyeC3L |  |
| 1,102,146 | 22.3 | 49.36 ms | 1 | DLMM -> DAMM | Mriya | Mriya |
| 899,389 | 138.1 | 6.51 ms | 1 | DLMM -> Pump | gtagyESa |  |
| 879,451 | 17.4 | 50.58 ms | 1 | CLMM -> DLMM | Mriya | Mriya |
| 679,606 | 48.2 | 14.09 ms | 1 | CLMM -> DLMM -> Pump | 7xhYhQm4 |  |
| 435,871 | 30.9 | 14.12 ms | 1 | DLMM -> Pump | Dtvmxr | Dtvm |
| 428,242 | 20.9 | 20.54 ms | 1 | CLMM -> DLMM | Dtvmxr | Dtvm |
| 425,410 | 12.2 | 34.82 ms | 1 | CLMM -> Orca | Dtvmxr | Dtvm |
| 166,820 | 48.4 | 3.45 ms | 1 | RayV4 -> CPMM -> Orca -> DLMM | gtagyESa |  |
| 159,922 | 14.6 | 10.95 ms | 1 | CPMM -> CLMM -> DLMM | Mriya | Mriya |
| 154,079 | 15.9 | 9.69 ms | 1 | DLMM -> Pump | Dtvmxr | Dtvm |
| 138,280 | 13.7 | 10.09 ms | 1 | DLMM -> Pump | Dtvmxr | Dtvm |
| 109,107 | 24.5 | 4.46 ms | 1 | CLMM -> DLMM | 7dGrdJRY |  |
| 107,347 | 25.2 | 4.25 ms | 1 | CPMM -> DLMM | AQ3MK4mf |  |
| 100,264 | 22.5 | 4.46 ms | 1 | Pump -> DAMM | 9EwQoN74 |  |
| 90,667 | 23.4 | 3.87 ms | 1 | CPMM -> Orca -> DLMM -> Pancake | Mriya | Mriya |
| 82,749 | 16.3 | 5.06 ms | 1 | CPMM -> DLMM -> Manifest -> Pancake | gtagyESa |  |
| 77,853 | 11.6 | 6.70 ms | 1 | DLMM -> Pump | E3yE42dQ |  |
| 77,577 | 23.6 | 3.29 ms | 1 | DLMM -> Pump | 327677Xq |  |
| 74,442 | 12.3 | 6.06 ms | 1 | DLMM -> DAMM | 2QfBNK2W |  |
| 70,191 | 15.8 | 4.45 ms | 1 | CPMM -> DLMM -> Manifest | gtagyESa |  |
| 69,768 | 10.2 | 6.86 ms | 1 | CPMM -> DLMM | E3yE42dQ |  |
| 62,981 | 101.9 | 0.62 ms | 1 | DLMM -> DAMM | Dtvmxr | Dtvm |
| 59,606 | 42.2 | 1.41 ms | 1 | CPMM -> DLMM | CzYQ2kFn |  |
| 56,062 | 91.7 | 0.61 ms | 1 | Orca -> DLMM | 7dGrdJRY |  |
| 42,676 | 11.5 | 3.71 ms | 1 | DLMM -> Pump | Dtvmxr | Dtvm |

Uncaptured residual alpha (N with no successful searcher) is not in this census.
