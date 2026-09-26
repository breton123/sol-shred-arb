# EXEC-LIVE-001 — live route0 program

Frozen `route0.c` / `route0.h` / EXEC-002 template were not mutated.
The program lives beside them: `arb-exec/program`.

```
OUR_EXEC
  → real Meteora DLMM swap2
  → real PumpSwap sell / buy_exact_quote_in
  → profit guard (quote_after >= quote_before + min_profit)
```

Instruction is still 25 bytes: `ARBEXEC0 | dir | amount_in | min_profit`.
Accounts 0–34 are the frozen vector. 35 is Token-2022. 36–57 are the live Pump IDL metas.

## What landed

| Item | Status |
|------|--------|
| Pinocchio executor (`arb-exec/program`) | written, builds |
| SBF size | 7648 B (`--arch v0 --optimize-size`) / 13672 B (default tools) |
| Profit guard | on-chain `Custom(6)` after both CPIs |
| Dedicated program key | `6xfcHyCsRkqbeJhX3RVd4gfHmTcQ6UWUhcP5cfGGrWNg` |
| Mainnet executable | **no** |
| Live `simulateTransaction` / CU | **not recorded** |
| 51k shim CU | discarded for fee planning; no replacement yet |

Live pair (same as LIVE-001):

| | pubkey |
|--|--------|
| DLMM | `DAErPzgiYQDhDwpMRgdvikXaZmnmznc3du3jy9i1AABk` |
| Pump | `BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs` |
| token | `7GUnr7krtQhJwd6ASY2VUprd9t4c64zcgCsjdmZepump` (Token-2022) |
| quote | WSOL |

Wallet used: `HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX` (from `.env`).

## Why it is not executable yet

The wallet had **0.091 SOL**. Loader-v3 deploy peaks at ~2× program rent (buffer + programdata). 13.6 KB ≈ 0.070 SOL rent → peak ≈ 0.14 SOL. That does not fit.

A Loader-v2 (BPF2) create_account was attempted as a single-account path. SIMD-0093 is active: BPF2 Write/Finalize return `UnsupportedProgramId`. The create already succeeded:

| | |
|--|--|
| account | `6xfcHyCsRkqbeJhX3RVd4gfHmTcQ6UWUhcP5cfGGrWNg` |
| owner | `BPFLoader2111111111111111111111111111111111` |
| lamports | 70,104,000 (0.070 SOL) |
| executable | no |
| recoverable | no (loader management disabled; no close) |

Leftover on the wallet after that create: **~0.021 SOL**. Not enough for a loader-v3 deploy of the same binary.

A local `solana-test-validator` clone of the live DLMM/Pump programs came up, but Agave 4.2 rejected the ELF (`sbpf_version required by the executable which are not enabled`) even for `--arch v0` / platform-tools v1.43. That path did not produce a CU number either.

## Live CPI notes (for the next deploy)

Pump `sell` disc `33e685a4017f83ad`, 24 bytes, 22–24 accounts.
Pump `buy_exact_quote_in` disc `c62e1552b4d9e870`, 24 bytes.
DLMM `swap2` disc `414b3f4ceb5b5b88` + `amount_in` + `min_out` + empty `RemainingAccountsInfo`.
This pair: no bitmap (pass DLMM program id), Token-2022 on X, Tokenkeg on Y, two bin arrays around `active_id`.

## What to do next (no more BPF2)

Fund the same wallet with **≥ 0.15 SOL** (covers loader-v3 peak + ATA + 0.00001 WSOL wrap + fees).

Then, from a machine with `solana` CLI:

```bash
solana program deploy arb-exec/program/target/deploy/route0.so \
  --program-id arb-exec/.deploy/program-v3.json \
  --use-rpc
python arb-exec/scripts/exec_live001.py
```

`exec_live001.py` will only simulate. It never `sendTransaction`s the arb.
The guard test is `amount_in = 10000` lamports and `min_profit = 1 SOL`.
If both hops succeed, the tx must revert `Custom(6)` and `unitsConsumed` is the live CU.

Do not reuse `6xfcHyCs…` as the program id. That account is a dead BPF2 shell.

Keys stay in `arb-exec/.deploy/` (gitignored). Never commit `.env`.
