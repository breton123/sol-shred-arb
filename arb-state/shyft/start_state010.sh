#!/bin/bash
# STATE-010: transaction-complete publication barriers.
# Restarts state008 only. Paper overlay soak stays. FUNDED=0.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-state/shyft/txexpect.py \
  /home/louis/arb-state/shyft/txbarrier.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/test_state010.py \
  /home/louis/arb-state/shyft/test_shadow.py
python3 -m py_compile \
  /home/louis/arb-state/shyft/txexpect.py \
  /home/louis/arb-state/shyft/txbarrier.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/shadow.py
( cd /home/louis/arb-state/shyft && python3 -m unittest test_state010 test_shadow )
mkdir -p /home/louis/captures/state008 /home/louis/captures/state008/mismatch
ts=$(date -u +%Y%m%dT%H%M%SZ)
if [[ -f /home/louis/captures/state008/SHADOW.jsonl ]]; then
  mv /home/louis/captures/state008/SHADOW.jsonl \
     "/home/louis/captures/state008/SHADOW.pre_s010.${ts}.jsonl"
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
pgrep -af "state008.py" || echo "S008_MISSING"
pgrep -a paper_orbit || echo "PAPER_MISSING"
pgrep -af "python3 hops_live.py recover" || echo "RECOVER_UNTOUCHED"
ls -l /dev/shm/arb_auth009 || echo "SHM_MISSING"
tail -10 /home/louis/captures/state008/state008.log || true
