#!/bin/bash
echo "=== PGREP ==="
pgrep -a feed || true
pgrep -a live || true
echo
echo "=== PS ==="
ps aux | grep -E 'feed|8001' | grep -v grep || true
echo
echo "=== SOCKET ==="
ss -ulnp || true
echo
echo "=== LOG ==="
ls -la /tmp/feed_live_8001.log 2>/dev/null || true
tail -n 20 /tmp/feed_live_8001.log 2>/dev/null || true
echo
echo "=== CAPTURES ==="
ls -la /home/louis/captures 2>/dev/null || true
echo
echo "=== DISK ==="
df -h /home/louis
echo
echo "=== BIN ==="
ls -la /home/louis/arb-feed/build/ 2>/dev/null || true
