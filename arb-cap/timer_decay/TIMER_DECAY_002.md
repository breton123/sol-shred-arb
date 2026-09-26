# TIMER-DECAY-002 — recon.bin replay

PAPER. Read-only walk of `/home/louis/captures/paper_orbit/recon.bin`. STATE-010 / paper_orbit were not modified. No sends.

The live 12-minute shadow (TIMER-DECAY-001) scheduled from already-coherent pools. This replay schedules at every AUTH, which is the honest “does the next write beat the clock?” test.

## Coverage

`recon.bin` is 565 MB. The reader stops at a zero-length record at 257 MB. Usable AUTH clocks:

| | |
|---|---|
| t0–t1 | 1790356126 – 1790372086 |
| Hours | **4.43** |
| AUTH records | 309 361 (DLMM + Pump) |
| Scheduled boundaries | 131 504 |
| Universe | idx ≤ 170 → 171-pool gen; after first idx > 170 → 645-pool gen |

The file ends ~75 minutes before the live shadow. No overlap. The last hour of the journal is the 645-pool era and produced only 12 survived boundaries.

## Funnel

| Stage | N |
|---|---:|
| Scheduled (every AUTH that had a future filter/decay and a Pump partner) | 131 504 |
| Survived to the clock with no later DLMM AUTH | 439 (0.33%) |
| Partner Pump also untouched | 407 |
| Fee rate actually fell | 426 (97% of survivors) |
| Route crossed `net ≤ 0` → `net > hurdle` | **4** |
| Account event at the crossing | **0 / 4** |
| Known searcher / MEV.live taker | **0 / 4** |

Almost every scheduled timer is cancelled by the next pool write. That is why 12 live minutes (pools already sitting mid-wait) looked like 19% survival, and 4.4 hours of AUTH-reset schedules look like 0.33%. Both numbers are true. They measure different start conditions.

## Opened net

4 crossings. Best-size net after hurdle:

| Pool | Era | Size | Net after | Lifetime | Close |
|---|---|---:|---:|---:|---|
| `E27r15wB…` | 171 | 1 SOL | +0.00249 SOL | 1 s | next write |
| `2gXV31km…` | 171 | 2 SOL | +0.00200 SOL | 1 s | next write |
| `GiRNCYDd…` | 171 | 1 SOL | **+0.01933 SOL** | 1 s | next write |
| `2gXV31km…` | 171 | 0.50 SOL | +0.00001 SOL | 17 s | STATE_UNCERTAIN |

Theoretical sum (best size each): **0.02383 SOL** in 4.43 h.

Distribution of those four nets (lamports): p50 2 002 176, p90 2 487 861, max 19 329 365. n=4. Do not treat p90 as a market.

All four were `filter` (vol halved), all `pump-dlmm`. `decay` (vol → 0) produced 35 survivors and **zero** crossings.

## Sizes

Best size on the four openings: 0.50 / 1 / 1 / 2 SOL.

Size-level crossings (a route can count in several sizes): 0.05, 0.10, 0.25, 0.50, 1, 2 each appear twice. The fat GiRNCYDd opening is +EV from 0.05 through 2 SOL; its optimum is 1 SOL. E27r15wB is already +EV at 0.05 after the timer, but the 1 SOL clip is the one that clears a large hurdle gap.

A 0.05-only probe would have caught 2 of 4 events and missed most of the dollars.

## Repeated pools

`2gXV31km…` opened twice in this journal and once in the live 12 minutes. `GiRNCYDd…` opened once here and once live. Those two pools are the only repeats so far. Not a universe-wide effect. A small set of high-vol DLMM/Pump pairs.

## Lifetime vs live shadow

Replay openings lived **1 s, 1 s, 1 s, 17 s**. Live openings lived **51 s and ≥125 s**.

The live jobs were scheduled from state that had already been quiet long enough to be near the boundary. The replay jobs start at AUTH, when `last_upd` resets. The next write usually arrives about when the filter clock fires.

Actionable time after an AUTH-reset timer is usually a second, not a minute. The long-lived cases exist; they are the exception, and they are how the 12-minute soak found 51–125 s.

## Combined with TIMER-DECAY-001 (no overlap)

| | Replay 4.43 h | Live 12 min | Together |
|---|---:|---:|---:|
| Crossings | 4 | 2 | 6 |
| Theoretical net | 0.02383 SOL | 0.00166 SOL | 0.0255 SOL |
| Known taker | 0 | 0 | 0 |
| Non-event at cross | 4/4 | 2/2 | 6/6 |

Naive together rate is ~0.0055 SOL/h. Do not annualize. One 1-second 0.019 SOL print is most of the replay dollars.

## 645-pool era

12 survived boundaries, 0 crossings. The journal barely covers the expanded universe. “How many crossings on 645 once coherence is good?” is still unanswered. Need a later recon that actually runs for hours at 645.

## Classification (unchanged)

**TIMER_DECAY: real mechanism, real +EV crossings, no labeled taker in this sample, economics still unproven at scale.**

Keep PAPER. Do not fund. The next useful hour of data is a continuous recon after the 645-pool univ, not another 12-minute live attach.
