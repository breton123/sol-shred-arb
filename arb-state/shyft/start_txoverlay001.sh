#!/bin/bash
# TX-OVERLAY-001: companion-wait + IX_EXACT/TX_EXACT overlay.
# AUTH SHM stays. FUNDED=0. Does not touch hops_live / recover_pda3 / ONESHOT.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-feed/src/tx_overlay.c \
  /home/louis/arb-feed/include/tx_overlay.h \
  /home/louis/arb-feed/src/paper_orbit.c \
  /home/louis/arb-feed/CMakeLists.txt
python3 -m py_compile \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/state008.py
( cd /home/louis/arb-state/shyft && python3 -m unittest test_shadow )
cmake --build /home/louis/arb-feed/build --target paper_orbit -j"$(nproc)"
mkdir -p /home/louis/captures/state008 /home/louis/captures/state008/mismatch
ts=$(date -u +%Y%m%dT%H%M%SZ)
if [[ -f /home/louis/captures/state008/SHADOW.jsonl ]]; then
  mv /home/louis/captures/state008/SHADOW.jsonl \
     "/home/louis/captures/state008/SHADOW.pre_txo.${ts}.jsonl"
fi
for pid in $(pgrep -f "arb-state/shyft/state008.py" || true); do
  comm=$(tr '\0' ' ' < "/proc/$pid/cmdline" || true)
  case "$comm" in
    *state008.py*) kill "$pid" || true; echo "stopped state008 $pid" ;;
  esac
done
sleep 1
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
if [[ -f /home/louis/.arb-state007.env ]]; then
  # shellcheck disable=SC1091
  . /home/louis/.arb-state007.env
fi
set +a
nohup python3 /home/louis/arb-state/shyft/state008.py \
  >> /home/louis/captures/state008/state008.log 2>&1 < /dev/null &
echo "state008 $!"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if [[ -f /home/louis/captures/state008/READY ]] && [[ -f /dev/shm/arb_auth009 ]]; then
    echo "READY after ${i}s"
    break
  fi
  sleep 1
done
for pid in $(pgrep -f '/home/louis/arb-feed/.*/paper_orbit' || true); do
  kill "$pid" || true
  echo "stopped paper $pid"
done
sleep 2
for pid in $(pgrep -f '/home/louis/arb-feed/.*/paper_orbit' || true); do
  kill -9 "$pid" || true
done
export PAPER_SECONDS=43200
export PAPER_SYNC="${HOME}/captures/paper_orbit/sync_state006.bin"
nohup /home/louis/arb-feed/scripts/paper_orbit.sh \
  >> /home/louis/captures/paper_orbit/paper_state009.log 2>&1 < /dev/null &
echo "paper $!"
sleep 3
pgrep -af "state008.py" || echo "S008_MISSING"
pgrep -a paper_orbit || echo "PAPER_MISSING"
pgrep -af "python3 hops_live.py recover" || echo "RECOVER_UNTOUCHED"
ls -l /dev/shm/arb_auth009 || echo "SHM_MISSING"
tail -8 /home/louis/captures/state008/state008.log || true
grep -E 'UNIV-GEN|AUTH-PUBLISH|FAIL|tx_exact' /home/louis/captures/paper_orbit/paper_state009.log | tail -n 8 || true
