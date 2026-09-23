#!/usr/bin/env bash
# NIC-004: AF_XDP copy-mode on veth-rx (parse → redirect → XSKMAP → UMEM).
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COUNT=${COUNT:-1000000}
SIZE=${SIZE:-1200}
PORT=${PORT:-9000}
BATCH=${BATCH:-32}
DEV=${DEV:-veth-rx}
QUEUE=${QUEUE:-0}

if [[ "${EUID}" -ne 0 ]]; then
    echo "bench_xsk.sh: run as root (sudo)" >&2
    exit 1
fi
if [[ ! -x "${ROOT}/build/xskbench" || ! -x "${ROOT}/build/txgen" ]]; then
    echo "bench_xsk.sh: build first (need xskbench + txgen)" >&2
    exit 1
fi

NPROC=$(nproc)
RXCPU=${RXCPU:-$((NPROC > 1 ? NPROC - 1 : 0))}
TXCPU=${TXCPU:-$((NPROC > 1 ? NPROC - 2 : 0))}
if [[ "${RXCPU}" -eq "${TXCPU}" && "${NPROC}" -gt 1 ]]; then
    TXCPU=0
    RXCPU=1
fi

OUTDIR=$(mktemp -d /tmp/arb-nic-xsk.XXXXXX)
"${ROOT}/scripts/setup_veth.sh"

cleanup() {
    "${ROOT}/build/xdpctl" detach --dev "${DEV}" >/dev/null 2>&1 || true
    "${ROOT}/scripts/teardown_veth.sh" || true
    rm -rf "${OUTDIR}"
}
trap cleanup EXIT

echo
echo "========== AF_XDP copy  dev=${DEV} queue=${QUEUE} rxcpu=${RXCPU} txcpu=${TXCPU} count=${COUNT} =========="

"${ROOT}/build/xskbench" \
    --dev "${DEV}" \
    --queue "${QUEUE}" \
    --count "${COUNT}" \
    --cpu "${RXCPU}" \
    --mlock \
    --idle-ms 2000 \
    --first-ms 15000 \
    >"${OUTDIR}/xsk.out" 2>"${OUTDIR}/xsk.err" &
XSKPID=$!

ready=0
for _ in $(seq 1 50); do
    if ! kill -0 "${XSKPID}" 2>/dev/null; then
        echo "xskbench exited before ready" >&2
        cat "${OUTDIR}/xsk.err" >&2 || true
        wait "${XSKPID}" || true
        exit 1
    fi
    if grep -q 'xskbench: ready' "${OUTDIR}/xsk.err" 2>/dev/null; then
        ready=1
        break
    fi
    sleep 0.1
done
if [[ "${ready}" -ne 1 ]]; then
    echo "xskbench did not print ready" >&2
    cat "${OUTDIR}/xsk.err" >&2 || true
    exit 1
fi

ip netns exec txns "${ROOT}/build/txgen" \
    --count "${COUNT}" \
    --size "${SIZE}" \
    --dst 10.10.0.1 \
    --port "${PORT}" \
    --cpu "${TXCPU}" \
    --batch "${BATCH}"

wait "${XSKPID}"
echo "----- xskbench stderr -----"
cat "${OUTDIR}/xsk.err"
echo "----- xskbench -----"
cat "${OUTDIR}/xsk.out"
echo
echo "done. path=veth+AF_XDP_COPY  RX cpu ${RXCPU}  TX cpu ${TXCPU}"
