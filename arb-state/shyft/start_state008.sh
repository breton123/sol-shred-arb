#!/bin/bash
# Replace STATE-007 writer only. recover_pda3 and paper stay up. FUNDED=0.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-state/shyft/deps.py \
  /home/louis/arb-state/shyft/submap.py \
  /home/louis/arb-state/shyft/authpub.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/state008.py \
  /home/louis/arb-state/shyft/run_state008.sh
python3 -m py_compile \
  /home/louis/arb-state/shyft/deps.py \
  /home/louis/arb-state/shyft/submap.py \
  /home/louis/arb-state/shyft/authpub.py \
  /home/louis/arb-state/shyft/shadow.py \
  /home/louis/arb-state/shyft/state008.py
chmod +x /home/louis/arb-state/shyft/run_state008.sh
mkdir -p /home/louis/captures/state008 /home/louis/captures/state008/mismatch
# kill only state008; paper + recover_pda3 stay up
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
sleep 2
pgrep -af "python3 hops_live.py recover" || echo "RECOVER_UNTOUCHED"
pgrep -af "paper_orbit" || echo "PAPER_UNTOUCHED"
pgrep -af "state008.py" || echo "S008_MISSING"
pgrep -af "state007.py" || echo "S007_GONE"
tail -12 /home/louis/captures/state008/state008.log || true
