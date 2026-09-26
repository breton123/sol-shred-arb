#!/bin/bash
echo "=== PROCESS ==="
pgrep -a feed_live || echo "feed_live not running"
echo
echo "=== SOCKET ==="
ss -ulnp | grep 8001 || echo "nothing on 8001"
echo
echo "=== CAPTURES ==="
ls -la /home/louis/captures
echo
echo "=== DISK ==="
df -h /home/louis
echo
echo "=== LOG TAIL ==="
tail -n 15 /tmp/feed_live_8001.log 2>/dev/null || true
echo
echo "=== LAST CAP GROW ==="
CAP=$(ls -1t /home/louis/captures/shredstream-*.cap | head -n 1)
echo "latest $CAP"
s1=$(stat -c%s "$CAP")
sleep 2
s2=$(stat -c%s "$CAP")
echo "size $s1 -> $s2  delta=$((s2-s1))"
