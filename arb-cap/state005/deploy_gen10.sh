#!/bin/bash
# GEN10 + searchable seq journal. #6 stays armed.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /home/louis/arb-feed/src/paper_orbit.c \
  /home/louis/arb-feed/scripts/paper_orbit.sh \
  /home/louis/arb-cap/state005/typed_score.py \
  /home/louis/arb-cap/state005/expand_gen10.py \
  /home/louis/arb-cap/state005/agg_searchable.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
cd /home/louis/arb-feed
cmake -S . -B build >/tmp/gen10_cmake.log 2>&1
cmake --build build --target paper_orbit
export UNIV_GEN_LOCKED=1
python3 /home/louis/arb-cap/state005/expand_gen10.py
python3 - <<'PY'
import os, signal
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"build/paper_orbit" in cmd or b"state005/state006.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 1
: > /home/louis/captures/paper_orbit/pending.jsonl
python3 -c "import struct,pathlib; pathlib.Path('/home/louis/captures/paper_orbit/recon.bin').write_bytes(struct.pack('<IHH',0x36305453,1,0))"
export PAPER_SECONDS=43200
export PAPER_UNIV=/home/louis/captures/paper_orbit/liveuniv.bin
export PAPER_SYNC=/home/louis/captures/paper_orbit/sync_state006.bin
export PAPER_PEND=/home/louis/captures/paper_orbit/pending.jsonl
export PAPER_RECON=/home/louis/captures/paper_orbit/recon.bin
nohup sh -c '/home/louis/arb-feed/scripts/paper_orbit.sh >> /home/louis/captures/paper_orbit/paper_state006.log 2>&1' \
  </dev/null >/tmp/paper_nohup.out 2>&1 &
echo "paper $!"
sleep 1
nohup python3 /home/louis/arb-cap/state005/state006.py \
  >> /home/louis/captures/paper_orbit/state006.log 2>&1 < /dev/null &
echo "state006 $!"
sleep 5
echo "=== paper ==="
tail -n 10 /home/louis/captures/paper_orbit/paper_state006.log
echo "=== oneshot ==="
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED || echo ARMED_MISSING
python3 /home/louis/arb-cap/state005/agg_searchable.py || true
pgrep -af "oneshot_live.py|exec_swqos_racer|feed_live|paper_orbit|state006.py" | grep -v grep || true
