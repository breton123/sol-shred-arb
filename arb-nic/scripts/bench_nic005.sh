#!/usr/bin/env bash
# NIC-005: one X710 LACP slave, UDP/39001 only, COPY then optional ZEROCOPY.
# Never attach both slaves — that blackholes bond0 / SSH / ICMP.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DEV=${DEV:?set DEV to one slave: eno1np0 or eno2np1 — not both, not bond0}
PORT=${PORT:-39001}
QUEUE=${QUEUE:-0}
COUNT=${COUNT:-1000000}
MODE=${MODE:-copy}
NTUPLE_LOC=${NTUPLE_LOC:-6}

if [[ "${EUID}" -ne 0 ]]; then
    echo "bench_nic005.sh: run as root (sudo)" >&2
    exit 1
fi
if [[ ! -x "${ROOT}/build/xskbench" ]]; then
    echo "bench_nic005.sh: build xskbench first" >&2
    exit 1
fi
if [[ "${DEV}" != eno1np0 && "${DEV}" != eno2np1 ]]; then
    echo "bench_nic005.sh: DEV must be a single bond slave, not bond0" >&2
    exit 1
fi

if [[ "${ARB_NIC_DAEMON:-}" != 1 ]]; then
    mkdir -p "${ROOT}/results"
    LOG="${ROOT}/results/nic005-${MODE}.log"
    echo "bench_nic005: detaching (XDP attach can drop SSH on this slave)" >&2
    echo "bench_nic005: log ${LOG}" >&2
    ARB_NIC_DAEMON=1 nohup env \
        DEV="${DEV}" MODE="${MODE}" COUNT="${COUNT}" PORT="${PORT}" \
        QUEUE="${QUEUE}" NTUPLE_LOC="${NTUPLE_LOC}" \
        "${ROOT}/scripts/bench_nic005.sh" >"${LOG}" 2>&1 &
    echo "bench_nic005: pid $!" >&2
    exit 0
fi
trap '' HUP

NPROC=$(nproc)
RXCPU=${RXCPU:-$((NPROC > 1 ? NPROC - 1 : 0))}
OUTDIR=$(mktemp -d /tmp/arb-nic-005.XXXXXX)
READY="${ROOT}/results/nic005.ready"
XSKPID=""
rm -f "${READY}"
pkill -x xskbench 2>/dev/null || true
sleep 0.2

ethtool -K "${DEV}" ntuple on >/dev/null 2>&1 || true
ethtool -N "${DEV}" delete "${NTUPLE_LOC}" 2>/dev/null || true
ethtool -N "${DEV}" flow-type udp4 dst-port "${PORT}" action "${QUEUE}" loc "${NTUPLE_LOC}"
echo "ntuple ${DEV} dest-port ${PORT} → q${QUEUE} loc ${NTUPLE_LOC}"
ethtool -n "${DEV}"
if ! ethtool -n "${DEV}" | grep -q "Dest port: ${PORT}"; then
    echo "bench_nic005.sh: ntuple dest-port ${PORT} did not install" >&2
    exit 1
fi

cleanup() {
    rm -f "${READY}"
    if [[ -n "${XSKPID}" ]]; then
        kill "${XSKPID}" 2>/dev/null || true
        wait "${XSKPID}" 2>/dev/null || true
    fi
    "${ROOT}/build/xdpctl" detach --dev "${DEV}" >/dev/null 2>&1 || true
    ethtool -N "${DEV}" delete "${NTUPLE_LOC}" 2>/dev/null || true
    rm -rf "${OUTDIR}"
}
trap cleanup EXIT

ZC=()
if [[ "${MODE}" == zerocopy ]]; then
    ZC=(--zerocopy)
elif [[ "${MODE}" != copy ]]; then
    echo "bench_nic005.sh: MODE=copy|zerocopy" >&2
    exit 1
fi

echo
echo "========== NIC-005  ${MODE}  ${DEV} q${QUEUE} port=${PORT} cpu=${RXCPU} count=${COUNT} =========="

"${ROOT}/build/xskbench" \
    --dev "${DEV}" \
    --queue "${QUEUE}" \
    --port "${PORT}" \
    --count "${COUNT}" \
    --cpu "${RXCPU}" \
    --mlock \
    --remote \
    --first-ms 600000 \
    --idle-ms 15000 \
    "${ZC[@]}" \
    >"${OUTDIR}/xsk.out" 2>"${OUTDIR}/xsk.err" &
XSKPID=$!

ready=0
for _ in $(seq 1 100); do
    if ! kill -0 "${XSKPID}" 2>/dev/null; then
        echo "xskbench exited before ready" >&2
        cat "${OUTDIR}/xsk.err" >&2 || true
        exit 1
    fi
    if grep -q 'xskbench: ready' "${OUTDIR}/xsk.err" 2>/dev/null; then
        ready=1
        break
    fi
    sleep 0.1
done
if [[ "${ready}" -ne 1 ]]; then
    echo "xskbench did not become ready" >&2
    cat "${OUTDIR}/xsk.err" >&2 || true
    exit 1
fi

echo "${XSKPID}" > "${READY}"
echo "xskbench ready — SEND NOW pid=${XSKPID} ${DEV}"
echo "COUNT=${COUNT} PORT=${PORT} RATE=3000 /mnt/c/Users/louis/Desktop/TheMoneyMaker/arb-nic/scripts/send_nic005.sh"

wait "${XSKPID}"
mkdir -p "${ROOT}/results"
cp -f "${OUTDIR}/xsk.err" "${ROOT}/results/nic005-${MODE}.err"
cp -f "${OUTDIR}/xsk.out" "${ROOT}/results/nic005-${MODE}.out"
echo "----- xskbench stderr -----"
cat "${OUTDIR}/xsk.err"
echo "----- xskbench -----"
cat "${OUTDIR}/xsk.out"
echo "saved ${ROOT}/results/nic005-${MODE}.out"
