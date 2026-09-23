#!/usr/bin/env bash
# Create:  txns (veth-tx 10.10.0.2)  <->  host (veth-rx 10.10.0.1)
set -euo pipefail

NS=txns
VETH_TX=veth-tx
VETH_RX=veth-rx
TX_IP=10.10.0.2
RX_IP=10.10.0.1

if [[ "${EUID}" -ne 0 ]]; then
    echo "setup_veth.sh: run as root (sudo)" >&2
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=/dev/null
"${SCRIPT_DIR}/teardown_veth.sh"

ip netns add "${NS}"
ip link add "${VETH_TX}" type veth peer name "${VETH_RX}"
ip link set "${VETH_TX}" netns "${NS}"

ip netns exec "${NS}" ip addr add "${TX_IP}/24" dev "${VETH_TX}"
ip netns exec "${NS}" ip link set "${VETH_TX}" up
ip netns exec "${NS}" ip link set lo up
ip netns exec "${NS}" ip link set "${VETH_TX}" txqueuelen 10000

ip addr add "${RX_IP}/24" dev "${VETH_RX}"
ip link set "${VETH_RX}" up
ip link set "${VETH_RX}" txqueuelen 10000

# Larger kernel UDP buffers so unlimited txgen is less likely to drop.
# Best-effort: some environments (user ns, locked sysctl) cannot raise these.
sysctl -q -w net.core.rmem_max=268435456 2>/dev/null || true
sysctl -q -w net.core.wmem_max=268435456 2>/dev/null || true
ip netns exec "${NS}" sysctl -q -w net.core.wmem_max=268435456 2>/dev/null || true

echo
echo "veth ready"
echo "  ${NS}: ${VETH_TX} ${TX_IP}/24"
echo "  host:  ${VETH_RX} ${RX_IP}/24"
echo
echo "Run the sender with:"
echo "  sudo ip netns exec txns ./build/txgen --count 10000000 --size 1200 --dst 10.10.0.1 --port 9000"
echo
