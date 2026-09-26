#!/bin/bash
# PUMP-AUTH-016 FASTSOAK from zero. Frozen 20260925 soak is not touched.
# Paper stays. FUNDED=0. CAP on /data (home is tight).
set -euo pipefail
CAP=/data/bsc/captures/soak_pump016_20260926/state008
export STATE008_CAP="$CAP"
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-state/shyft/txexpect.py \
  /home/louis/arb-state/shyft/txbarrier.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/overlay_n.py \
  /home/louis/arb-state/shyft/deps.py \
  /home/louis/arb-state/shyft/submap.py \
  /home/louis/arb-state/shyft/apply_n.py \
  /home/louis/arb-state/shyft/test_state010.py \
  /home/louis/arb-state/shyft/test_shadow.py \
  /home/louis/arb-state/shyft/test_fastsoak.py \
  /home/louis/arb-state/shyft/test_overlay_n.py
python3 -m py_compile \
  /home/louis/arb-state/shyft/txexpect.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/overlay_n.py \
  /home/louis/arb-state/shyft/deps.py
( cd /home/louis/arb-state/shyft && python3 -m unittest test_state010 test_shadow test_fastsoak test_overlay_n )
mkdir -p "$CAP/mismatch"
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
export STATE008_CAP="$CAP"
export STATE_APPLY=/home/louis/arb-core/build/state_apply
export FUNDED=0
nohup env STATE008_CAP="$CAP" STATE_APPLY="$STATE_APPLY" FUNDED=0 \
  python3 /home/louis/arb-state/shyft/state008.py \
  >> "$CAP/state008.log" 2>&1 < /dev/null &
echo "state008 $! CAP=$CAP"
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 30; do
  if [[ -f "$CAP/READY" ]]; then
    echo "READY after ${i}s"
    break
  fi
  sleep 1
done
pgrep -af "state008.py" || echo "S008_MISSING"
pgrep -a paper_orbit || echo "PAPER_MISSING"
test -x /home/louis/arb-core/build/state_apply && echo APPLY_OK || echo APPLY_MISSING
tail -20 "$CAP/state008.log" || true
