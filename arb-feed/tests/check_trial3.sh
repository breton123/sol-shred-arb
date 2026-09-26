#!/bin/bash
set -euo pipefail
CAP=/home/louis/captures/shredstream-20260923-231015.cap
LOG=/tmp/feed_live_8001.log
PID=2555936

echo "=== PROCESS ==="
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
ss -ulnp | grep 8001 || true
echo
echo "=== RATE ==="
L1=$(tail -n 1 "${LOG}")
echo "t0  ${L1}"
sleep 3
L2=$(tail -n 1 "${LOG}")
echo "t3  ${L2}"
echo
echo "=== INSPECT ==="
python3 /tmp/inspect_live.py "${CAP}"
echo
echo "=== SNAPSHOT REPLAY ==="
dd if="${CAP}" of=/tmp/feedcap_sample.cap bs=1M count=32 status=none
/home/louis/arb-feed/build/feed_replay --file /tmp/feedcap_sample.cap
echo
echo "=== DISK ==="
df -h /home/louis
ls -la /home/louis/captures
echo
echo "=== DONE ==="
