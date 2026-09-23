#!/usr/bin/env bash
# WSL / home sender for NIC-005. Unique dest port only — nothing else.
set -euo pipefail

DST=${DST:-195.242.152.178}
PORT=${PORT:-39001}
COUNT=${COUNT:-10000}
SIZE=${SIZE:-1200}
RATE=${RATE:-3000}
SPORT=${SPORT:-25000}

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WAIT_READY=${WAIT_READY:-1}
WAIT_SSH=${WAIT_SSH:-louis@195.242.152.178}
WAIT_READY_FILE=${WAIT_READY_FILE:-/home/louis/arb-nic/results/nic005.ready}
WAIT_KEY=${WAIT_KEY:-}
if [[ -z "${WAIT_KEY}" ]]; then
    for k in "${HOME}/.ssh/id_ed25519_arb" "${HOME}/.ssh/id_ed25519" /mnt/c/Users/louis/.ssh/id_ed25519; do
        if [[ -f "${k}" ]]; then
            WAIT_KEY=${k}
            break
        fi
    done
fi

if [[ "${WAIT_READY}" == 1 ]]; then
    echo "send_nic005: waiting for live xskbench ready on ${WAIT_SSH} (start the Frankfurt bench if you have not)" >&2
    ready=0
    for _ in $(seq 1 360); do
        if ssh -o BatchMode=yes -o ConnectTimeout=5 -i "${WAIT_KEY}" "${WAIT_SSH}" \
            "test -s '${WAIT_READY_FILE}' && pgrep -x xskbench >/dev/null"; then
            ready=1
            break
        fi
        sleep 1
    done
    if [[ "${ready}" -ne 1 ]]; then
        echo "send_nic005: xskbench never became ready — not sending" >&2
        exit 1
    fi
    echo "send_nic005: ready — blasting now" >&2
fi

if [[ -x "${ROOT}/build/txgen" ]]; then
    echo "send_nic005: txgen  $COUNT x $SIZE B  → ${DST}:${PORT}  sport=${SPORT}  rate=${RATE}"
    exec "${ROOT}/build/txgen" \
        --count "${COUNT}" \
        --size "${SIZE}" \
        --dst "${DST}" \
        --port "${PORT}" \
        --sport "${SPORT}" \
        --rate "${RATE}"
fi

echo "send_nic005: python  $COUNT x $SIZE B  → ${DST}:${PORT}  sport=${SPORT}  rate=${RATE}"
python3 - "${DST}" "${PORT}" "${COUNT}" "${SIZE}" "${RATE}" "${SPORT}" <<'PY'
import socket, struct, sys, time
dst, port, count, size, rate, sport = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
size = max(size, 16)
interval = 1.0 / rate if rate > 0 else 0.0
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if sport:
    s.bind(("0.0.0.0", sport))
print(f"send_nic005: bound {s.getsockname()} → {dst}:{port}", file=sys.stderr)
pad = b"\0" * (size - 16)
t0 = time.perf_counter()
for i in range(count):
    if interval:
        target = t0 + i * interval
        now = time.perf_counter()
        if now < target:
            time.sleep(target - now)
    # sequence + placeholder send_ns (ignored on --remote)
    s.sendto(struct.pack("!QQ", i, 0) + pad, (dst, port))
print(f"sent {count} to {dst}:{port} from {s.getsockname()}", file=sys.stderr)
PY
