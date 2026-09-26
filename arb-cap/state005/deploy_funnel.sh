#!/bin/bash
# Rebuild paper_orbit with searchable funnel. Leave ONESHOT#6 alone.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-feed/src/paper_orbit.c \
  /home/louis/arb-feed/CMakeLists.txt
cd /home/louis/arb-feed
cmake -S . -B build >/tmp/funnel_cmake.log 2>&1
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
    if b"build/paper_orbit" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 0.8
export PAPER_SECONDS=43200
export PAPER_UNIV=/home/louis/captures/paper_orbit/liveuniv.bin
export PAPER_SYNC=/home/louis/captures/paper_orbit/sync_state006.bin
export PAPER_PEND=/home/louis/captures/paper_orbit/pending.jsonl
export PAPER_RECON=/home/louis/captures/paper_orbit/recon.bin
nohup sh -c '/home/louis/arb-feed/scripts/paper_orbit.sh >> /home/louis/captures/paper_orbit/paper_state006.log 2>&1' \
  </dev/null >/tmp/paper_nohup.out 2>&1 &
echo "paper $!"
sleep 6
echo "=== paper ==="
tail -n 16 /home/louis/captures/paper_orbit/paper_state006.log
echo "=== oneshot ==="
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_MISSING
pgrep -af "oneshot_live.py|exec_swqos_racer|feed_live|paper_orbit|state006.py" | grep -v grep || true
