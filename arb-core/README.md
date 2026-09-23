# arb-core

What these bytes mean, and whether there is money.

`arb-nic` answers "what bytes arrived?" and stops at `rx_packet_t`. This tree consumes that boundary. Replay today; DoubleZero / AF_XDP later. The remaining ~95% does not care.

```text
35k recorded shreds
        ↓
arb-core replay
        ↓
shred_view          frozen
        ↓
relevance           CLASSIFY-002
        ↓
CORE-001            shred → affected pool   ← next
```

Do not scaffold quoting, routes, or an executor here.

## CLASSIFY-002

Same two 32-byte IDs (Meteora DLMM, PumpSwap). Scalar control, AVX2, AVX-512. Two-byte discriminator at offsets +0 and +7, then full 32-byte verify. Objective is `min T_reject`.

```bash
cd ~/arb-core
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target replay
./build/replay --file ~/arb-nic/data/shreds.arbrx --scanner all --loops 8 --warmup 35512 --cpu 47 --mlock
```

Counts must stay bit-identical: DLMM 4560, Pump 39520, both 536, irrelevant 240552.

## Layout

```text
include/     shred, rx_packet_t, classify
src/         classify.c (scalar / AVX2 / AVX-512)
tests/       replay
```
