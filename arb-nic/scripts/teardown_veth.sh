#!/usr/bin/env bash
# Remove the txns namespace and veth pair created by setup_veth.sh.
set -euo pipefail

NS=txns
VETH_TX=veth-tx
VETH_RX=veth-rx

if [[ "${EUID}" -ne 0 ]]; then
    echo "teardown_veth.sh: run as root (sudo)" >&2
    exit 1
fi

# Drop any XDP program before deleting the pair.
if ip link show "${VETH_RX}" >/dev/null 2>&1; then
    ip link set "${VETH_RX}" xdp off 2>/dev/null || true
    ip link set "${VETH_RX}" xdpdrv off 2>/dev/null || true
    ip link set "${VETH_RX}" xdpgeneric off 2>/dev/null || true
fi

ip netns del "${NS}" 2>/dev/null || true
ip link del "${VETH_RX}" 2>/dev/null || true
ip link del "${VETH_TX}" 2>/dev/null || true

echo "veth torn down (namespace ${NS}, ${VETH_TX}, ${VETH_RX})"
