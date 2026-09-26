#!/bin/bash
set -euo pipefail
CAP=/home/louis/captures/shredstream-20260923-231015.cap
LOG=/tmp/feed_live_8001.log
PID=$(pgrep -n -f '/home/louis/arb-feed/build/feed_live')

echo "=== PROCESS ==="
if [ -z "${PID}" ]; then
  echo "FAIL  feed_live not running"
  exit 1
fi
ps -o pid,psr,pcpu,pmem,rss,nlwp,etime,cmd -p "${PID}"
echo
echo "=== AFFINITY ==="
taskset -cp "${PID}" || true
for t in /proc/"${PID}"/task/*; do
  tid=${t##*/}
  echo -n "tid=${tid} "
  taskset -cp "${tid}" || true
done
echo
echo "=== SOCKET ==="
ss -ulnp | grep -E '8001|39902' || true
echo
echo "=== LISTENERS ==="
pgrep -a feed_live || true
echo
echo "=== DISK ==="
df -h /home/louis
du -h /home/louis/captures
ls -la /home/louis/captures
echo
echo "=== LOG1 ==="
tail -n 8 "${LOG}"
sleep 3
echo
echo "=== LOG2 ==="
tail -n 8 "${LOG}"
echo
echo "=== INSPECT ==="
python3 /tmp/inspect_live.py "${CAP}"
echo
echo "=== SNAPSHOT REPLAY ==="
dd if="${CAP}" of=/tmp/feedcap_sample.cap bs=1M count=32 status=none
/home/louis/arb-feed/build/feed_replay --file /tmp/feedcap_sample.cap
echo
echo "=== DONE ==="
