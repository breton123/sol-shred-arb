#!/bin/bash
# STATE-010-FASTSOAK: restart state008 only. Paper stays. FUNDED=0.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-state/shyft/txexpect.py \
  /home/louis/arb-state/shyft/txbarrier.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/apply_n.py \
  /home/louis/arb-state/shyft/test_state010.py \
  /home/louis/arb-state/shyft/test_shadow.py \
  /home/louis/arb-state/shyft/test_fastsoak.py
python3 -m py_compile \
  /home/louis/arb-state/shyft/txexpect.py \
  /home/louis/arb-state/shyft/txbarrier.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/apply_n.py
( cd /home/louis/arb-state/shyft && python3 -m unittest test_state010 test_shadow test_fastsoak )
mkdir -p /home/louis/captures/state008 /home/louis/captures/state008/mismatch
ts=$(date -u +%Y%m%dT%H%M%SZ)
if [[ -f /home/louis/captures/state008/METRICS.json ]]; then
  cp /home/louis/captures/state008/METRICS.json \
     "/home/louis/captures/state008/METRICS.pre_fastsoak.${ts}.json"
  echo "baseline METRICS.pre_fastsoak.${ts}.json"
fi
if [[ -f /home/louis/captures/state008/SHADOW.jsonl ]]; then
  mv /home/louis/captures/state008/SHADOW.jsonl \
     "/home/louis/captures/state008/SHADOW.pre_fastsoak.${ts}.jsonl"
fi
if [[ -f /home/louis/captures/state008/FIRST_MISMATCH.json ]]; then
  mv /home/louis/captures/state008/FIRST_MISMATCH.json \
     "/home/louis/captures/state008/FIRST_MISMATCH.pre_fastsoak.${ts}.json"
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
export STATE_APPLY=/home/louis/arb-core/build/state_apply
nohup python3 /home/louis/arb-state/shyft/state008.py \
  >> /home/louis/captures/state008/state008.log 2>&1 < /dev/null &
echo "state008 $!"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 30; do
  if [[ -f /home/louis/captures/state008/READY ]] && [[ -f /dev/shm/arb_auth009 ]]; then
    echo "READY after ${i}s"
    break
  fi
  sleep 1
done
pgrep -af "state008.py" || echo "S008_MISSING"
pgrep -a paper_orbit || echo "PAPER_MISSING"
test -x /home/louis/arb-core/build/state_apply && echo APPLY_OK || echo APPLY_MISSING
tail -15 /home/louis/captures/state008/state008.log || true
