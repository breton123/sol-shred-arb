# Case study: `4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK`

Trial window + 200k-signature floor through 2026-09-24 12:54 UTC. Public-wallet reconstruction. Helius enhanced history 403'd; funding walk from birth was not reached.

## What it is

A **second Mriya-class occupant**, not a Mriya clone.

Same latency fingerprint on premium shreds (173/173 immediate races, actionable N and their first bytes arrive together; 99% of trial arbs are immediate). Completely different execution stack: two **third-party** upgradeable executors, no durable nonce, ~0.4% on-chain fail, 100% 2-hop, almost only DLMM→Pump, ~25 SOL sitting on the wallet.

## Fingerprint vs Mriya

| | Mriya | 4BQ6AT |
|---|---|---|
| Immediate / act=0 | 74% (706/956) | **100% (173/173)** |
| Custom program | `AN225` — this wallet is upgrade authority | `MEViEnsc…` + `CGGqPC3…` — **other** authorities |
| Nonce | ~992 durable, advance-first | **none** (System ix is `transfer`, not `advanceNonce`) |
| On-chain fail | 55–64% | **0.40%** (792/200000). Sampled fails are Pump.fun `6EF8…`, not the arb path |
| Hops | 2/3/4+ | **100% 2-hop** (182/182 trial) |
| Route | broad | **169/182 DLMM → Pump** |
| Landing | `none` 93% + Jito overlay | `none`; base fee 5000 lamports; prio fee $0; tip p50 **$0.12** |
| Tick p50 | ~30 | **29** |
| Capital on wallet | ~1,400 SOL + $140k stables | **25.46 SOL** + dust ATAs |
| First activity | 2026-09-03 (wallet birth) | **≤ 2026-07-31** (200k-sig floor; still the same arb template) |
| Leaders (trial) | global | spread; Frankfurt 50/182 of labeled slots |

There are at least two independent ways into the pre-shred seat. 4BQ6AT is the **precision** one (single route, almost never miss, tiny inventory). Mriya is the **spray** one (nonce pool, high fail, multi-hop, fat book).

## Programs

Top-level template, newest through oldest in the 200k window:

`ComputeBudget, ComputeBudget, System.transfer, {MEViEnsc | CGGqPC3}`

Inner: Meteora DLMM `LBUZ…`, Pump `pAMMBay…`, SPL token, Pump fee `pfeeUx…`.

| Program | Upgrade authority | Notes |
|---|---|---|
| `MEViEnscUm6tsQRoGd9h6nLQaQspKj7DB2M5FwM3Xvz` | `SMB6JY59jr4JJCDdSt5uBD6DPEYX7VFKKJbCubvHV91` | 96/182 trial arbs. Not 4BQ6AT. |
| `CGGqPC3oERK5a7X38ttJGVTdR1YCSm53nxTMrhAvBRJX` | `6HG7FCcdN3yEt8LGbyS9XcwqCTAV6ktWuPETS84tYJdu` | 86/182 trial arbs. Not 4BQ6AT. |
| `AN225yk…` | — | **0** in 76 parsed samples |

They consume a shared/vendor executor. They did not deploy their own AN225.

## Trial window (3h18m)

182 labeled successes, $1,060 net. 169 DLMM→Pump, 8 CPMM→DLMM, 4 DLMM→DAMM v2. Provider field empty on MEV.live (GAME_RECON previously: `none` 100%). Leaders: binance staking 10, Figment 8, Helius 7, Bitwise 7 — not a pet of one name. Cities: Frankfurt 50, Amsterdam 28, London 15.

## Capital / first activity

DAS snapshot: 25.46 native SOL, no USDC/USDT pile, leftover memecoin ATAs are cents. They recycle a small SOL stack through the 2-hop. The 200k newest signatures still look like the arb template at 2026-07-31 22:32 UTC — wallet birth and any CEX funder sit **before** that floor. Enhanced-API funding walk was 403.

## Why this matters

Mriya is not a one-off accident. A second shop occupies the same shred-simultaneous class with a **different** machine: no nonce spray, no custom program they own, almost no fails, one route. Pre-sequencing (or an earlier view of N) is the shared ingredient. The executor is not.
