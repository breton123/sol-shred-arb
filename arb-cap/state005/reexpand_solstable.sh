#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/expand6/expand_framed.py /tmp/expand6/expand_keep6.sh
cp /tmp/expand6/expand_framed.py /home/louis/arb-cap/state005/expand_framed.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
export UNIV_GEN_LOCKED=1
python3 /home/louis/arb-cap/state005/expand_framed.py
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
nohup /home/louis/arb-feed/scripts/paper_orbit.sh \
  >> /home/louis/captures/paper_orbit/paper_state006.log 2>&1 < /dev/null &
echo "paper $!"
sleep 1
nohup python3 /home/louis/arb-cap/state005/state006.py \
  >> /home/louis/captures/paper_orbit/state006.log 2>&1 < /dev/null &
echo "state006 $!"
sleep 5
echo "=== paper ==="
tail -n 10 /home/louis/captures/paper_orbit/paper_state006.log
echo "=== procs ==="
pgrep -c -f build/paper_orbit || true
pgrep -af "oneshot_live|exec_swqos_racer|feed_live|paper_orbit|state006.py" | grep -v grep || true
python3 - <<'PY'
import json, os
j = json.load(open("/home/louis/captures/paper_orbit/liveuniv.json"))
print({k: j.get(k) for k in ("gen", "n", "n_dlmm", "n_pump", "n_cpmm", "added_dlmm")})
print("ARMED", os.path.exists("/home/louis/arb-cap/oneshot/ARMED"))
PY
