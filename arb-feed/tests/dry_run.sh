#!/bin/bash
set -e
cd ~/arb-feed
rm -rf /tmp/feedcap
mkdir -p /tmp/feedcap
./build/feed_live --bind 127.0.0.1 --port 39902 --out /tmp/feedcap --prefix dry --min-gb 1 --rotate-bytes 1048576 >/tmp/feed_live.err 2>&1 &
echo $! > /tmp/feed_live.pid
sleep 0.4
python3 - <<'PY'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
p = bytearray(200)
p[64] = 0x90
p[65] = 1
for i in range(20):
    s.sendto(p, ("127.0.0.1", 39902))
s.close()
PY
sleep 0.6
kill -INT "$(cat /tmp/feed_live.pid)" || true
sleep 0.5
echo "--- live ---"
cat /tmp/feed_live.err
echo "--- files ---"
ls -l /tmp/feedcap
echo "--- replay ---"
f=$(ls -1 /tmp/feedcap/dry-*.cap | head -1)
./build/feed_replay --file "$f"
