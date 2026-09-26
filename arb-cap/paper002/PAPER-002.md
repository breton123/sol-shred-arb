# PAPER-002

Economic truth audit. PAPER-LIVE-001 **PnL is void**. Latency stands.

## Verdict: FAIL — chronology

- `liveuniv.bin` slot **450112763** (S_today, fetched 2026-09-24)
- FEEDCAP1 slots **449848541–449891196**
- delta **264222 slots** (~29 h). We quoted 2026-09-24 state against 2026-09-23 shreds.
- That is `S_today`, not `S_{slot=N-1}`.

Throw away: searchable $762k, UNCLAIMED $123k, could_have_raced $83k, ratio p50=72.7.

## Phantoms

### $0.61 × 377,971
- family 0, route_id 1, amount_in 822222222 (0.822 SOL), gross 5336841 lamports
- trigger pool_idx 0 or 38: `ENiVH49XwRM3Cu9n4Tp6CGynCFXf3Mz6CE3GRmVk1LH4 (pump 0)` / `4MjpgAT7H8GmWsZDUaeGUNZwjur8n8sKCSPHHjQRE4sm (dlmm 38)`
- `cycle_size` on **today's** top pair. Same size, same gp, every shred. N was not applied (`hot_decode` failed on raw payload).

### $352.96 × 1,297
- family OTHER, route_id 126, 3-hop proto Pump→DAMM→DAMM `[2, 5, 5]`
- amount_in 8333333333 (8.333 SOL), gross 3069199485 lamports
- pools: `5PGhKctym6odbHGo2tKMST2AjmJsb2uZBQrKkn4ZuFT5 (pump 76)`, `3WZUnUVQwFVSod5dxk99g9PyQRhSTNkLdb3uYRt19Kw1 (damm 74)`
- **This is exactly the 1297 rows ≥ $50 and ≥ $100.** One stale 3-hop on S_today.

## 20 DLMM→Pump winners

| slot | them $ | S_pump | hist base/quote | today base/quote | trigger N | winner DLMM ain | verdict |
|------|--------|--------|-----------------|------------------|-----------|-----------------|---------|
| 449862874 | $444.72 | S_PRETOKEN (slot N trigger/winner pre) | 47809771712808/409541048632 | 29995135770712/819797451937 | 60781283827 | 25131697117 | READY_FOR_KERNEL |
| 449871626 | $385.39 | S_PRETOKEN (slot N trigger/winner pre) | 30032788640175/696824757946 | 30008264874347/819431816457 | 3515286658413 | 1987252812828 | READY_FOR_KERNEL |
| 449874881 | $249.94 | S_PRETOKEN (slot N trigger/winner pre) | 38883673291389/544109588372 | 30008264874347/819431816457 | 2952736328253 | 2193103637161 | READY_FOR_KERNEL |
| 449850496 | $144.57 | VAULTS_NOT_IN_TX | - | 29330273443221/1341729610001 | - | 697737325554 | PUMP_HIST_MISSING |
| 449855968 | $138.09 | S_PRETOKEN (slot N trigger/winner pre) | 54845045620225/332353354190 | 29995033047449/819801791232 | 8650869979317 | 4341873262019 | READY_FOR_KERNEL |
| 449871268 | $91.18 | S_PRETOKEN (slot N trigger/winner pre) | 30125323385958/692991867864 | 30025162188488/818963185592 | 1660568481909 | 1194078715119 | READY_FOR_KERNEL |
| 449881406 | $91.07 | S_PRETOKEN (slot N trigger/winner pre) | 116695815792588/179288066429 | 108911816118302/196987610961 | 12160618521132 | 5350427508960 | READY_FOR_KERNEL |
| 449880573 | $89.28 | S_PRETOKEN (slot N trigger/winner pre) | 98730889993551/1396275124600 | 100562384468035/1373302217610 | 1201065413677 | 906471652601 | READY_FOR_KERNEL |
| 449860504 | $88.90 | VAULTS_NOT_IN_TX | - | 30025874905287/818943368380 | - | 2365791644697 | PUMP_HIST_MISSING |
| 449874678 | $87.26 | S_PRETOKEN (slot N trigger/winner pre) | 37191155089883/566005339121 | 30026614819420/818922795936 | 3336073844894 | 2309542704281 | READY_FOR_KERNEL |
| 449861145 | $85.89 | VAULTS_NOT_IN_TX | - | 30026614819420/818922795936 | 6460843852 | 12261206542 | PUMP_HIST_MISSING |
| 449871348 | $79.79 | S_PRETOKEN (slot N trigger/winner pre) | 31072918832404/671867978496 | 30026614819420/818922795936 | 1660568481910 | 1241781080419 | READY_FOR_KERNEL |
| 449889173 | $65.15 | VAULTS_NOT_IN_TX | - | 55323471316621/480489377869 | 341235455 | 1831955225742 | PUMP_HIST_MISSING |
| 449882106 | $63.15 | VAULTS_NOT_IN_TX | - | 30025618010433/818950681171 | - | 283721113790 | PUMP_HIST_MISSING |
| 449859495 | $61.12 | S_PRETOKEN (slot N trigger/winner pre) | 50335711198418/379372061838 | 30025618010433/818950681171 | 2386801879434 | 8283321664 | READY_FOR_KERNEL |
| 449855967 | $57.10 | S_PRETOKEN (slot N trigger/winner pre) | 55052405495579/330891046301 | 30123310422672/816243153583 | 4806038877398 | 2627417146358 | READY_FOR_KERNEL |
| 449862613 | $57.00 | VAULTS_NOT_IN_TX | - | 30113237373405/816522631521 | 50412133087 | 1230852597940 | PUMP_HIST_MISSING |
| 449862712 | $56.05 | S_PRETOKEN (slot N trigger/winner pre) | 43959790452770/556694951460 | 35251665107672/712660614602 | 1643980154285 | 1121241952357 | READY_FOR_KERNEL |
| 449863882 | $55.58 | S_PRETOKEN (slot N trigger/winner pre) | 32052032045128/2693515743231 | 31545461355125/2742847273799 | 813045418080 | 252887964082 | READY_FOR_KERNEL |
| 449860128 | $46.40 | S_PRETOKEN (slot N trigger/winner pre) | 52786381310364/362730066635 | 30117327551990/816409579525 | 2145764626752 | 1139292973249 | READY_FOR_KERNEL |

S_dlmm bins are **S_today** on every row (RPC cannot return account bytes at slot N-1).
S_pump vaults **are** recoverable from `preTokenBalances` when the vaults appear in the trigger/winner.

## One print walked: slot 449862874  them $444.72

Same pools the $0.61 phantom sits on: DLMM `ET9QEc18` + Pump `ENiVH49X`.

Winner `amount_in` (DLMM hop) = 25.131697117 SOL.

Trigger was Pump, not DLMM. N on Pump vaults: base −5.90e12, quote +60.30 SOL.

| state | cycle_size | quote at winner 25.13 SOL |
|-------|------------|---------------------------|
| S_today (both venues, slot 450112763) | 0.644 SOL in → +0.00059 SOL ($0.07) | dir0 **−3.22 SOL**, dir1 **−1.46 SOL** |
| S_pump hist (preToken) + S_dlmm **today** | 20 SOL in → +36.4 SOL ($4,186) | dir0 **−18.2 SOL**, dir1 invalid |

S_today says the size that printed $444 was a **loss**. Mixed hist-pump still cannot reproduce the hop because DLMM bins are yesterday+29h.

Pump reserves actually moved:

| | hist (pre N) | today |
|--|--------------|-------|
| base | 47.81e12 | 30.00e12 |
| quote | 409.5 SOL | 819.8 SOL |

14/20 winners had recoverable Pump `preTokenBalances`. 0/20 had DLMM bins at slot N−1 (RPC will not return account bytes for a past slot).

Audit does not pass until `cycle_size(S_dlmm_{N-1}, S_pump_{N-1})` matches the winner hop amounts.

## What would pass

Historical canonical S for both venues at `slot=N-1`:

- Pump: vault `preTokenBalances` (this works when the vaults are in the tx)
- DLMM: LbPair + bin arrays as of N−1 — **not available from `getTransaction`**. Need a recorder that snapshots those accounts in the capture window, or an archival account-data source.

Do not resume paper PnL, UNCLAIMED, or could_have_raced until that exists.
