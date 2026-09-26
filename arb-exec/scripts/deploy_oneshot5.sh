#!/bin/bash
# Deploy CORE-010 live gate + arm ONESHOT #5. Keep journals. Leave feed_live.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/paper_orbit.c \
  /tmp/CMakeLists_feed.txt \
  /tmp/oneshot_live.py \
  /tmp/run_oneshot.sh \
  /tmp/restart_paper_keep.sh \
  /tmp/frame.c \
  /tmp/frame.h
cp /tmp/paper_orbit.c /home/louis/arb-feed/src/paper_orbit.c
cp /tmp/CMakeLists_feed.txt /home/louis/arb-feed/CMakeLists.txt
cp /tmp/frame.c /home/louis/arb-core/src/frame.c
cp /tmp/frame.h /home/louis/arb-core/include/frame.h
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/run_oneshot.sh /home/louis/arb-exec/scripts/run_oneshot.sh
cp /tmp/restart_paper_keep.sh /home/louis/arb-cap/state005/restart_paper_keep.sh
chmod +x /home/louis/arb-exec/scripts/run_oneshot.sh \
  /home/louis/arb-cap/state005/restart_paper_keep.sh
rm -f /home/louis/arb-cap/oneshot/ARMED
python3 - <<'PY'
import os, signal
needles = [b"scripts/oneshot_live.py"]
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if any(n in cmd for n in needles):
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid, cmd[:80])
PY
echo "=== rebuild paper_orbit (keep journals) ==="
bash /home/louis/arb-cap/state005/restart_paper_keep.sh
echo "=== arm ONESHOT#5 FUNDED=1 ==="
nohup bash /home/louis/arb-exec/scripts/run_oneshot.sh \
  >> /home/louis/arb-cap/oneshot/oneshot5.log 2>&1 &
echo "oneshot pid $!"
sleep 2
pgrep -af paper_orbit || true
pgrep -c feed_live || true
python3 - <<'PY'
import os
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\x00", b" ")
    except OSError:
        continue
    if b"oneshot_live" in cmd or b"trigger_outcomes" in cmd:
        print(pid, cmd.decode("utf-8", "replace")[:160])
PY
tail -n 20 /home/louis/arb-cap/oneshot/oneshot5.log || true
tail -n 8 /home/louis/captures/paper_orbit/paper_state006.log || true
