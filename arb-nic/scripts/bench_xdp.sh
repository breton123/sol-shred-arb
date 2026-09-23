#!/usr/bin/env bash
# NIC-002 workload under no-XDP / XDP_PASS / XDP-parse-pass.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if [[ "${EUID}" -ne 0 ]]; then
    echo "bench_xdp.sh: run as root (sudo) — XDP attach needs the veth pair" >&2
    exit 1
fi
if [[ ! -x "${ROOT}/build/xdpctl" ]]; then
    echo "bench_xdp.sh: build/xdpctl missing — cmake + make with clang/libbpf" >&2
    exit 1
fi

export XDP_MODES="${XDP_MODES:-none pass parse}"
exec "${ROOT}/scripts/bench_nic002.sh"
