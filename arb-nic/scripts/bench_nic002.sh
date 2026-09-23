#!/usr/bin/env bash
# Compare poll / busy / perf on the local veth pair (or loopback if not root).
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COUNT=${COUNT:-1000000}
SIZE=${SIZE:-1200}
PORT=${PORT:-9000}
BATCH=${BATCH:-32}
XDP_MODES=${XDP_MODES:-none}
XDP_IFACE=${XDP_IFACE:-veth-rx}

if [[ ! -x "${ROOT}/build/rxbench" || ! -x "${ROOT}/build/txgen" ]]; then
    echo "bench_nic002.sh: build first (cmake + make in ${ROOT}/build)" >&2
    exit 1
fi

NPROC=$(nproc)
RXCPU=${RXCPU:-$((NPROC > 1 ? NPROC - 1 : 0))}
TXCPU=${TXCPU:-$((NPROC > 1 ? NPROC - 2 : 0))}
if [[ "${RXCPU}" -eq "${TXCPU}" && "${NPROC}" -gt 1 ]]; then
    TXCPU=0
    RXCPU=1
fi

# Fresh dir owned by the current euid. Do not reuse /tmp files from another
# user — root cannot overwrite louis-owned files in sticky /tmp
# (fs.protected_regular).
OUTDIR=$(mktemp -d /tmp/arb-nic-bench.XXXXXX)

USE_VETH=0
DST=127.0.0.1
BIND=127.0.0.1
if [[ "${EUID}" -eq 0 ]]; then
    USE_VETH=1
    DST=10.10.0.1
    BIND=10.10.0.1
    "${ROOT}/scripts/setup_veth.sh"
else
    echo "bench_nic002.sh: not root — loopback 127.0.0.1 (veth needs sudo)"
fi

xdp_apply() {
    local kind=$1

    if [[ "${kind}" != "none" && "${USE_VETH}" -ne 1 ]]; then
        echo "bench_nic002.sh: XDP=${kind} needs root + veth" >&2
        return 1
    fi
    if [[ -x "${ROOT}/build/xdpctl" && "${USE_VETH}" -eq 1 ]]; then
        "${ROOT}/build/xdpctl" detach --dev "${XDP_IFACE}" >/dev/null 2>&1 || true
    fi
    case "${kind}" in
        none) ;;
        pass|parse)
            if [[ ! -x "${ROOT}/build/xdpctl" ]]; then
                echo "bench_nic002.sh: build/xdpctl missing (need clang + libbpf)" >&2
                return 1
            fi
            "${ROOT}/build/xdpctl" attach --dev "${XDP_IFACE}" --prog "${kind}"
            ;;
        *)
            echo "bench_nic002.sh: unknown XDP mode '${kind}' (none|pass|parse)" >&2
            return 1
            ;;
    esac
}

cleanup() {
    if [[ -x "${ROOT}/build/xdpctl" && "${USE_VETH}" -eq 1 ]]; then
        "${ROOT}/build/xdpctl" detach --dev "${XDP_IFACE}" >/dev/null 2>&1 || true
    fi
    if [[ "${USE_VETH}" -eq 1 ]]; then
        "${ROOT}/scripts/teardown_veth.sh" || true
    fi
    rm -rf "${OUTDIR}"
}
trap cleanup EXIT

wait_rx_ready() {
    local rxpid=$1
    local i
    for i in $(seq 1 50); do
        if ! kill -0 "${rxpid}" 2>/dev/null; then
            echo "rxbench exited before becoming ready" >&2
            return 1
        fi
        if ss -H -uln "sport = :${PORT}" 2>/dev/null | grep -q .; then
            return 0
        fi
        sleep 0.1
    done
    echo "rxbench did not bind :${PORT}" >&2
    return 1
}

run_mode() {
    local mode=$1
    local xdp_kind=${2:-none}
    local out="${OUTDIR}/rx-${xdp_kind}-${mode}.out"
    local err="${OUTDIR}/rx-${xdp_kind}-${mode}.err"
    local path_name

    if [[ "${USE_VETH}" -eq 1 ]]; then
        path_name=veth
    else
        path_name=loopback
    fi

    echo
    echo "========== xdp=${xdp_kind}  mode=${mode}  path=${path_name}  rxcpu=${RXCPU} txcpu=${TXCPU} count=${COUNT} =========="

    "${ROOT}/build/rxbench" \
        --mode "${mode}" \
        --cpu "${RXCPU}" \
        --batch "${BATCH}" \
        --count "${COUNT}" \
        --port "${PORT}" \
        --bind "${BIND}" \
        --idle-ms 2000 \
        --first-ms 15000 \
        >"${out}" 2>"${err}" &
    local rxpid=$!

    if ! wait_rx_ready "${rxpid}"; then
        echo "----- rxbench stderr -----" >&2
        cat "${err}" >&2 || true
        wait "${rxpid}" || true
        return 1
    fi

    if [[ "${USE_VETH}" -eq 1 ]]; then
        ip netns exec txns "${ROOT}/build/txgen" \
            --count "${COUNT}" \
            --size "${SIZE}" \
            --dst "${DST}" \
            --port "${PORT}" \
            --cpu "${TXCPU}" \
            --batch "${BATCH}"
    else
        "${ROOT}/build/txgen" \
            --count "${COUNT}" \
            --size "${SIZE}" \
            --dst "${DST}" \
            --port "${PORT}" \
            --cpu "${TXCPU}" \
            --batch "${BATCH}"
    fi

    wait "${rxpid}"
    echo "----- rxbench stderr -----"
    cat "${err}"
    echo "----- rxbench -----"
    cat "${out}"
}

for xdp_kind in ${XDP_MODES}; do
    xdp_apply "${xdp_kind}"
    run_mode poll "${xdp_kind}"
    run_mode busy "${xdp_kind}"
    run_mode perf "${xdp_kind}"
    if [[ "${xdp_kind}" != "none" && -x "${ROOT}/build/xdpctl" ]]; then
        echo "----- xdp stats (${xdp_kind}) -----"
        "${ROOT}/build/xdpctl" stats || true
        "${ROOT}/build/xdpctl" detach --dev "${XDP_IFACE}" >/dev/null 2>&1 || true
    fi
done

echo
if [[ "${USE_VETH}" -eq 1 ]]; then
    echo "done. path=veth  xdp=${XDP_MODES}  RX cpu ${RXCPU}  TX cpu ${TXCPU}"
else
    echo "done. path=loopback  xdp=${XDP_MODES}  RX cpu ${RXCPU}  TX cpu ${TXCPU}"
fi
