# arb-nic

v0 baseline plus **NIC-002**, **XDP_PASS / parse**, **NIC-004 AF_XDP copy-mode redirect**, and **NIC-005** (physical X710, COPY then forced ZEROCOPY).

Ultra-low-latency NIC/RX path that will later sit in front of a Solana arbitrage searcher.

Two receive paths:

```text
txgen → veth → [optional XDP_PASS] → UDP recvmmsg → rxbench
txgen → veth → XDP parse → XDP_REDIRECT → XSKMAP → AF_XDP UMEM → xskbench
```

No Solana. `XDP_ZEROCOPY` is NIC-005 on the physical X710, forced — no COPY fallback.

## What these numbers mean

**veth is a software-network benchmark. These latency numbers are NOT physical NIC latency.**

`txgen` stamps `send_ns` in userspace with `CLOCK_MONOTONIC_RAW`. `rxbench` stamps again in userspace after `recvmmsg()`. That interval includes:

* sender syscall / kernel UDP TX
* Linux veth (software)
* kernel UDP RX
* receiver syscall

It does **not** measure a physical NIC, DoubleZero, or XDP. The point of v0 is a small, explicit measurement and replay framework we can later swap the clock and the RX path in.

## Later target (not implemented)

```text
DoubleZero
    ↓
physical NIC
    ↓
XDP
    ↓
AF_XDP zero-copy
    ↓
owned CPU core
    ↓
arb hot path
```

Keep this tree small enough to inspect the generated assembly.

## Build

Linux, C17. Userspace benches have no extra libraries. XDP needs `clang` and `libbpf` (`xdpctl` + `xdp.bpf.o`).

```bash
mkdir build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j
```

Release flags: `-O3 -march=native -mtune=native`, plus `-Wall -Wextra -Wpedantic -Werror`.

## Run

From the repository root:

```bash
sudo ./scripts/setup_veth.sh
```

The script prints the sender command. Topology:

```text
tx namespace (txns)
     │
   veth-tx   10.10.0.2
     │
     │ Linux veth
     │
   veth-rx   10.10.0.1
     │
 host namespace
```

Terminal 1 (host), pin RX to a different core than TX:

```bash
./build/rxbench --mode busy --cpu 3 --batch 32 --count 1000000 --port 9000
```

Terminal 2 (tx netns):

```bash
sudo ip netns exec txns ./build/txgen \
    --count 1000000 \
    --size 1200 \
    --dst 10.10.0.1 \
    --port 9000 \
    --cpu 2 \
    --batch 32
```

Or run the three-mode comparison (poll / busy / perf):

```bash
sudo ./scripts/bench_nic002.sh
```

XDP comparison (same NIC-002 workload, three attaches):

```bash
sudo ./scripts/bench_xdp.sh
```

That is `XDP_MODES="none pass parse"` × poll/busy/perf. **XDP_PASS on veth is not a useful latency experiment** — it adds XDP and still walks the full IP/UDP/`recvmmsg` stack on a software device. Throughput can go up while p99 explodes. Do not read that as “XDP is slow.”

AF_XDP copy-mode (NIC-004), same 1M × 1200 B workload:

```bash
sudo ./scripts/bench_xsk.sh
```

`xskbench` (not `rxbench`) binds `veth-rx` queue 0, one UMEM, fill ring, then spins: peek RX → pointer → handle → recycle. Parser is Ethernet → IPv4 → UDP → configured dport. Match redirects into `XSKMAP`; everything else is `XDP_PASS`.

Tear down:

```bash
sudo ./scripts/teardown_veth.sh
```

`setup_veth.sh` calls teardown first, so rerunning setup after teardown (or after a half-finished setup) is safe.

## Packet

`include/packet.h`:

```c
struct test_packet {
    uint64_t sequence;
    uint64_t send_ns;
};
```

`--size` is the full UDP payload (default **1200** bytes). The 16-byte header sits at the front; the rest is padding so we can approximate shred-sized packets later. `sequence` and `send_ns` are network byte order on the wire.

## CLI

Both programs accept `--help`. Defaults:

| flag | txgen | rxbench |
| --- | --- | --- |
| `--count` | 1000000 | 1000000 |
| `--size` | 1200 | — |
| `--dst` / `--bind` | 10.10.0.1 | 0.0.0.0 |
| `--port` | 9000 | 9000 |
| `--rate` | 0 (unlimited) | — |
| `--cpu` | unset | unset |
| `--batch` | 1 (`sendmmsg`) | 32 (`recvmmsg`) |
| `--mode` | — | `poll` |

`rxbench` preallocates latency, sequence bitmap, and RDTSCP stage arrays **before** the receive loop. It stops after `--count` datagrams, or after `--idle-ms` (default 1000) with no packets once traffic has started.

Throughput `Gbps` is UDP payload bits over the first-to-last receive window.

## NIC-002

| mode | wait | notes |
| --- | --- | --- |
| `poll` | `poll(2)` then `recvmmsg` | default, v0-compatible |
| `busy` | userspace spin + `SO_BUSY_POLL` | burns one core |
| `perf` | same as busy | also `--quiet` + `mlockall`; no I/O in the hot path |

Pin TX and RX to **different** cores (`--cpu`). `perf record` example:

```bash
perf record -C 3 -- ./build/rxbench --mode perf --cpu 3 --count 1000000
```

`SO_BUSY_POLL` is most useful on a real NIC. On veth the main win is skipping `poll(2)` and batching with `recvmmsg`. Failure to set `SO_BUSY_POLL` is non-fatal; the spin loop still runs.

## NIC-004 (AF_XDP copy)

Removes IP / UDP / socket / `recvmmsg` from the arb path:

```text
veth → XDP parse → dport 9000? → XDP_REDIRECT → XSKMAP → UMEM → xskbench
```

Stages timed with RDTSCP: RX peek → packet pointer → handle → fill recycle. `empty_polls` counts the spin.

## NIC-005 (physical X710)

Stop treating veth pps as the goal.

```text
WSL
    ↓
Ethernet
    ↓
Intel X710
    ↓
DMA
    ↓
i40e native XDP
    ↓
dport 39001 ? XDP_REDIRECT : XDP_PASS
    ↓
AF_XDP UMEM
    ↓
CPU47
```

Home WSL → Frankfurt `195.242.152.178` UDP **39001** only. SSH and every other port stay in the kernel stack. Do not redirect generic UDP.

LACP: the public flow can land on `eno1np0` or `eno2np1`. Discover the slave for this 5-tuple **before** attaching XDP (no root needed):

```bash
# Frankfurt
./scripts/discover_slave.sh

# WSL, while that is listening
COUNT=20000 RATE=5000 ./scripts/send_nic005.sh
```

Measured flow (same home IPv4, dest 39001):

```text
81.147.105.164:58796  →  195.242.152.178:39001  →  eno1np0
```

20,000 / 20,000 userspace hits. Slave counters: `eno1np0` +20108, `eno2np1` +87 (background). Attach **only** `eno1np0`. Never `bond0`. Existing ntuple (loc 0–5: 8001/8003/8701/9001/9006/9007 → q0) is left alone. We add **loc 6** for dest-port 39001 → q0. loc 20 is not a usable i40e slot — without a real filter this flow RSSes to **q13**, and an XSK on q0 sees nothing.

```bash
# Frankfurt
sudo DEV=eno1np0 MODE=copy COUNT=1000000 ./scripts/bench_nic005.sh
sudo DEV=eno1np0 MODE=zerocopy COUNT=1000000 ./scripts/bench_nic005.sh

# WSL, when xskbench prints ready:
COUNT=1000000 PORT=39001 RATE=20000 ./scripts/send_nic005.sh
```

`XDP_PASS` on a LACP slave does not keep SSH alive — that 5-tuple also hashes to `eno1np0`. Non-match packets `bpf_redirect` into `bond0`. The bench detaches from the SSH tty (`nohup`) because native XDP attach can reset i40e rings and drop the session. Reconnect and `tail -f ~/arb-nic/results/nic005-copy.log`.

COPY first: remote sender → X710 → XDP → AF_XDP COPY → 1M sequence-correct. Then `--zerocopy` forces `XDP_ZEROCOPY` + native XDP. Bind failure is fatal — no COPY fallback.

Cross-machine `send_ns` is **not** a latency metric. Compare COPY vs ZEROCOPY on Frankfurt-local pps, drops, batch, handle/recycle cycles. Hardware RX timestamps are later.

## Timing

* **e2e latency:** `clock_gettime(CLOCK_MONOTONIC_RAW)` via `now_ns()` — the on-wire `send_ns` stamp.
* **stage timing:** `RDTSCP` via `rdtscp()`, calibrated to Hz at startup. Reports `recvmmsg` (per syscall) and `handle` (per packet after recv).

Do not sprinkle clocks through the hot path. Kernel / hardware RX timestamps are not implemented yet.
