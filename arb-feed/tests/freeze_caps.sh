#!/bin/bash
set -euo pipefail
PID=$(pgrep -n -f './build/feed_live')
if [ -n "${PID}" ]; then
  echo "SIGINT ${PID}"
  kill -INT "${PID}"
  for i in $(seq 1 20); do
    if ! kill -0 "${PID}" 2>/dev/null; then
      echo "stopped"
      break
    fi
    sleep 1
  done
  if kill -0 "${PID}" 2>/dev/null; then
    echo "still running after 20s"
    exit 1
  fi
else
  echo "feed_live already stopped"
fi
chmod a-w /home/louis/captures/shredstream-*.cap
mkdir -p /home/louis/captures/derived
cp -n /tmp/feed_live_8001.log /home/louis/captures/derived/feed_live_8001.log || true
echo "=== FROZEN ==="
ls -la /home/louis/captures/shredstream-*.cap | wc -l
du -h /home/louis/captures
ss -ulnp | grep 8001 || echo "8001 closed"
pgrep -a feed_live || echo "no feed_live"
