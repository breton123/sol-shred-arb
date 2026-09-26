# SHRED_V1_MARKET

3h18m premium shred window (`11913.7 s` = **3.309 h**). Successful MEV.live arbs only.
Do **not** annualize. `$ / hr` is this window only.

Headroom = `T(searcher first bytes) − T(N actionable)`. Local+send budget is **not** subtracted; read the sensitivity row for your measured `T_actionable→leader`.

**Scope of the join (this file):** every arb with `pure_profit ≥ $10` whose slot already had a slim block (`225 / 281`, **$10,995 / $12,448** of the fat book). `212` located both sides in the frozen capture. The remaining **54 fat slots ($1,453)** plus the entire **<$10 book ($7,593)** are still in the 34k-slot slim fetch. Uncaptured residual (N with nobody landing) is not in this census.

Competition counts from this slice are **not** usable: we did not load the <$10 searchers on the same trigger. Jackpot `competitors≤3` is therefore a **lower bound on solitude**, not a proof.

---

## Headlines

| | $ | $/hr |
|---|---:|---:|
| TOTAL SUCCESSFUL ARB $ (full 171,277) | **$20,041** | **$6,056/hr** |
| Fat tail ≥ $10 (281 arbs) | $12,448 | $3,761/hr |
| Fat located in capture (212) | $10,389 | $3,139/hr |
| SHRED-COMPETABLE fat, headroom ≥ 500 µs | **$1,697** | **$513/hr** |
| CURRENT UNIVERSE fat, DLMM+Pump ≥ 500 µs | **$807** | **$244/hr** |
| EXPANDED fat, +DAMM/CLMM/CPMM/Orca ≥ 500 µs | **$1,582** | **$478/hr** |

The two largest prints in the window (**$1,891** CLMM→Meteora Pools, **$635** and friends at `$500+`) have **~0 µs** headroom. They are pre-shred / simultaneous, not V1 inventory.

Dust (<$10) will only **raise** the shred-competable totals. Treat every capturable number below as a **lower bound**.

---

## Sensitivity — fat-tail competitor $ with enough headroom

Once we measure `T_actionable→leader`, read the column ≥ that budget.

| budget | all fat routes | route0 DLMM+Pump | expanded |
|---:|---:|---:|---:|
| 20 µs | $2,248 | $1,001 | $2,133 |
| 50 µs | $2,248 | $1,001 | $2,133 |
| 100 µs | $2,248 | $1,001 | $2,133 |
| 250 µs | $1,791 | $818 | $1,675 |
| **500 µs** | **$1,697** | **$807** | **$1,582** |
| 1 ms | $1,445 | $795 | $1,330 |
| 2 ms | $1,357 | $782 | $1,242 |
| 5 ms | $1,151 | $747 | $1,134 |
| 10 ms | $528 | $196 | $528 |

20 / 50 / 100 µs are identical: on this fat book the leftover pile starts after 100 µs. If we land at **180 µs**, we are still in the **$2,248 / $1,001 route0** row.

---

## Full-window route mix (no headroom — book shape only)

| route | n | $ |
|---|---:|---:|
| DLMM → Pump | 5,529 | **7,064** |
| CLMM → Meteora Pools | 79 | 1,892 |
| CPMM → DLMM | 1,205 | 1,590 |
| CLMM → DLMM → Pump | 815 | 1,091 |
| CLMM → Orca | 2,955 | 723 |
| CPMM → Orca → DLMM | 764 | 670 |
| Orca → DLMM | 3,881 | 632 |
| DLMM → DAMM v2 | 2,020 | 608 |
| DLMM only | 8,805 | 587 |
| CPMM → CLMM → DLMM | 917 | 568 |

DLMM→Pump is **35% of all successful $** before any timing cut.

---

## Fat located — dollars by route family × headroom

| route | n | all $ | 100µs | 250µs | 500µs | 1ms | 5ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| DLMM → Pump | 87 | 3,773 | 913 | 818 | **807** | 795 | 747 |
| CLMM → Meteora Pools | 1 | 1,891 | 0 | 0 | 0 | 0 | 0 |
| CPMM → DLMM | 16 | 789 | 114 | 78 | 78 | 78 | 10 |
| CLMM → Orca | 3 | 660 | 12 | 12 | 12 | 12 | 12 |
| CLMM → DLMM → Pump | 17 | 607 | 210 | 185 | 101 | 101 | 81 |
| Orca → DLMM | 7 | 371 | 292 | 92 | 92 | 0 | 0 |
| DLMM → DAMM | 7 | 279 | 136 | 136 | **136** | 35 | 35 |
| CPMM → CLMM → DLMM | 7 | 266 | 143 | 143 | 143 | 143 | 143 |

---

## Protocol addition ROI (fat, ≥ 500 µs)

| add | extra capturable $ | extra $/hr | cumulative |
|---|---:|---:|---:|
| A  DLMM + Pump | **+807** | +244/hr | 807 |
| B  + DAMM v2 | **+188** | +57/hr | 995 |
| C  + Raydium CLMM | **+248** | +75/hr | 1,243 |
| D  + Raydium CPMM | **+221** | +67/hr | 1,463 |
| E  + Orca | **+118** | +36/hr | 1,582 |

After route-0, **CLMM then CPMM then DAMM** are the next fat dollars, not Orca. 3-hop leftovers (CLMM→DLMM→Pump $101, CPMM→CLMM→DLMM $143) need a wider executor than route-0.

---

## Fat-tail thresholds (located)

| ≥ $ | n | $ | of which ≥ 500 µs n | ≥ 500 µs $ |
|---:|---:|---:|---:|---:|
| 10 | 212 | 10,389 | 39 | 1,697 |
| 25 | 84 | 8,379 | 15 | 1,307 |
| 50 | 41 | 6,904 | 8 | **1,050** |
| 100 | 14 | 4,983 | 4 | 754 |
| 250 | 4 | 3,356 | 1 | 385 |
| 500 | 2 | 2,526 | 0 | 0 |
| 1000 | 1 | 1,891 | 0 | 0 |

**16%** of located fat $ is shred-late (≥ 500 µs). The other **84%** is Mriya-class simultaneous.

---

## Jackpot  `profit ≥ $50  ∧  headroom ≥ 500 µs`

(competitors column omitted — fat-only sample cannot see <$10 rivals)

| profit | headroom | route | winner | Mriya | 4BQ | tick | leader |
|---:|---:|---|---|---|---|---:|---|
| 385.4 | 5.87 ms | DLMM → Pump | Mriya | Y |  | 9 | Bitwise |
| 138.1 | 6.51 ms | DLMM → Pump | gtagyE |  |  | 30 | HZKop… |
| 128.6 | 12.68 ms | CPMM → CLMM → DLMM | CatyeC3 |  |  | 47 | Bitwise / Jito BAM |
| 101.9 | 0.62 ms | DLMM → DAMM | Dtvmxr |  |  | 13 | HZKop… |
| 91.7 | 0.61 ms | Orca → DLMM | 7dGrdJ |  |  | 57 | Stardust |
| 85.9 | 27.41 ms | DLMM → Pump | Dtvmxr |  |  | 16 | oixpq… |
| 65.1 | 22.46 ms | DLMM → Pump | CatyeC3 |  |  | 46 | Next Finance Tech |
| 53.7 | 40.96 ms | CLMM | 888enCW |  |  | 34 | Kraken 2 |

≥ 1 ms and ≥ 5 ms are the same six rows after dropping the two ~0.6 ms DAMM/Orca prints: **$857**.

Mriya **can** be 6 ms late on a $385 DLMM→Pump. 4BQ does not appear in this jackpot list (consistent with 100% act=0 on their immediate book).

Elite-absent among fat winners with ≥ 500 µs: no Mriya **$1,149**; still $1,149 without 4BQ; **$837** after also dropping Dtvmxr.

---

## Slot-level elite exclusion (full 171k, **not** trigger groups)

| exclusion | slots | $ in those slots |
|---|---:|---:|
| no Mriya | 36,016 | 13,554 |
| no Mriya / 4BQ | 35,862 | 12,378 |
| no Mriya / 4BQ / Dtvmxr | 35,660 | 8,962 |

These are **slot** piles, not opportunity piles. Trigger-level elite-absent $ comes after the full slim join.

---

## What this says about OrbitFlare

Observed, fat-only, lower bound:

- route-0 shred-late ≥ 500 µs: **$244/hr**
- same at 5 ms (if TPU is sloppy): **$226/hr**
- expanded 5-venue ≥ 500 µs: **$478/hr**
- jackpot ≥ $50 and ≥ 500 µs: **$317/hr** ($1,050 / 3.309 h)

A $1k/month feed is **~$1.40/hr**. Even a small capture fraction of the $244/hr route-0 late fat book covers it — **if** we actually land inside that budget and `cycle_size` sees S'. That last if is still unproven (no historical DLMM bins).

The full 171k sensitivity (dust + remaining 54 fat slots) is still downloading slim blocks. It will raise the capturable $; it will not resurrect the $1,891 / $500+ simultaneous prints.

Uncaptured residual alpha (N with no successful searcher) is the next census after this one, and needs state replay.
