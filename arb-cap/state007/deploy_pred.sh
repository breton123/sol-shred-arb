#!/bin/bash
# Install mut_authoritative send predicate. FUNDED stays 0. No oneshot.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/s007/paper_orbit.c /tmp/s007/state007.py \
  /tmp/s007/oneshot_live.py /tmp/s007/agg_funnel007.py \
  /tmp/s007/audit_candidate.py /tmp/s007/STATE007.md
cp /tmp/s007/paper_orbit.c /home/louis/arb-feed/src/paper_orbit.c
cp /tmp/s007/state007.py /home/louis/arb-state/shyft/state007.py
cp /tmp/s007/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/s007/agg_funnel007.py /home/louis/arb-cap/state007/agg_funnel007.py
cp /tmp/s007/audit_candidate.py /home/louis/arb-cap/state007/audit_candidate.py
cp /tmp/s007/STATE007.md /home/louis/arb-cap/state007/STATE007.md
cd /home/louis/arb-feed
cmake --build build --target paper_orbit
python3 - <<'PY'
import os, signal
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"build/paper_orbit" in cmd or b"arb-state/shyft/state007.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 0.8
set -a
. /home/louis/.arb-smoke.env
. /home/louis/.arb-state007.env
set +a
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
sleep 10
echo "=== funded ==="
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_ABSENT; fi
grep FUNDED /home/louis/arb-exec/scripts/run_oneshot.sh
echo "=== s007 ==="
tail -n 8 /home/louis/captures/state007/state007.log
echo "=== paper ==="
tail -n 4 /home/louis/captures/paper_orbit/paper_state006.log
