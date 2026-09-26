#!/bin/bash
# STATE-007 deploy. FUNDED stays 0. Does not start oneshot.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/s007/fetch_proto.sh \
  /tmp/s007/deploy_state007.sh \
  /tmp/s007/state006.py \
  /tmp/s007/paper_orbit.c \
  /tmp/s007/run_oneshot.sh \
  /tmp/s007/agg_funnel007.py \
  /tmp/s007/disarm_funded.sh || true
mkdir -p /home/louis/arb-state/shyft /home/louis/arb-cap/state007 /home/louis/captures/state007
cp /tmp/s007/config.py /tmp/s007/submap.py /tmp/s007/recon.py /tmp/s007/state007.py \
   /tmp/s007/requirements.txt /tmp/s007/fetch_proto.sh \
   /home/louis/arb-state/shyft/
cp /tmp/s007/agg_funnel007.py /home/louis/arb-cap/state007/agg_funnel007.py
cp /tmp/s007/paper_orbit.c /home/louis/arb-feed/src/paper_orbit.c
cp /tmp/s007/state006.py /home/louis/arb-cap/state005/state006.py
cp /tmp/s007/run_oneshot.sh /home/louis/arb-exec/scripts/run_oneshot.sh
chmod +x /home/louis/arb-state/shyft/fetch_proto.sh
if [[ -f /tmp/s007/shyft.env ]]; then
  chmod 600 /tmp/s007/shyft.env
  cp /tmp/s007/shyft.env /home/louis/.arb-state007.env
  chmod 600 /home/louis/.arb-state007.env
  rm -f /tmp/s007/shyft.env
fi
export PATH="${HOME}/.local/bin:${PATH}"
python3 -m pip install --user --break-system-packages -q -r /home/louis/arb-state/shyft/requirements.txt
bash /home/louis/arb-state/shyft/fetch_proto.sh
# FUNDED=0
bash /tmp/s007/disarm_funded.sh || true
# rebuild paper
cd /home/louis/arb-feed
cmake --build build --target paper_orbit
python3 - <<'PY'
import os, signal
needles = (b"build/paper_orbit", b"state005/state006.py", b"arb-state/shyft/state007.py")
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if any(n in cmd for n in needles):
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 1
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
if [[ -f /home/louis/.arb-state007.env ]]; then
  # shellcheck disable=SC1091
  . /home/louis/.arb-state007.env
fi
set +a
nohup python3 /home/louis/arb-cap/state005/state006.py \
  >> /home/louis/captures/paper_orbit/state006.log 2>&1 < /dev/null &
echo "state006 $!"
nohup python3 /home/louis/arb-state/shyft/state007.py \
  >> /home/louis/captures/state007/state007.log 2>&1 < /dev/null &
echo "state007 $!"
export PAPER_SECONDS=43200
export PAPER_UNIV=/home/louis/captures/paper_orbit/liveuniv.bin
export PAPER_SYNC=/home/louis/captures/paper_orbit/sync_state006.bin
export PAPER_PEND=/home/louis/captures/paper_orbit/pending.jsonl
export PAPER_RECON=/home/louis/captures/paper_orbit/recon.bin
nohup sh -c '/home/louis/arb-feed/scripts/paper_orbit.sh >> /home/louis/captures/paper_orbit/paper_state006.log 2>&1' \
  </dev/null >/tmp/paper_nohup.out 2>&1 &
echo "paper $!"
sleep 12
echo "=== funded ==="
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_ABSENT
pgrep -c -f oneshot_live.py || echo 0
echo "=== state007 ==="
tail -n 20 /home/louis/captures/state007/state007.log
echo "=== paper ==="
tail -n 8 /home/louis/captures/paper_orbit/paper_state006.log
