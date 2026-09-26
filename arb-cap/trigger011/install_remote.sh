#!/usr/bin/env bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/t011src/alt_cache.h
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/t011src/trigger.h
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/t011src/alt_cache.c
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/t011src/trigger.c
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/t011src/trigger011.c
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/t011src/paper_orbit.c
cp /tmp/s007/t011src/alt_cache.h /home/louis/arb-core/include/alt_cache.h
cp /tmp/s007/t011src/trigger.h /home/louis/arb-core/include/trigger.h
cp /tmp/s007/t011src/alt_cache.c /home/louis/arb-core/src/alt_cache.c
cp /tmp/s007/t011src/trigger.c /home/louis/arb-core/src/trigger.c
cp /tmp/s007/t011src/trigger011.c /home/louis/arb-core/tests/trigger011.c
cp /tmp/s007/t011src/paper_orbit.c /home/louis/arb-feed/src/paper_orbit.c
mkdir -p /home/louis/captures/trigger011
mkdir -p /home/louis/arb-cap/trigger011
cmake --build /tmp/build-t011 --target trigger011 core010 -j4
/tmp/build-t011/trigger011
/tmp/build-t011/core010
cmake --build /home/louis/arb-feed/build --target paper_orbit -j4
# one paper only
for p in $(pgrep -f '/home/louis/arb-feed/build/paper_orbit' || true); do
  kill "$p" 2>/dev/null || true
done
sleep 1
for p in $(pgrep -f '/home/louis/arb-feed/build/paper_orbit' || true); do
  kill -9 "$p" 2>/dev/null || true
done
if ! pgrep -f 'alt_plane.py' >/dev/null; then
  nohup python3 /home/louis/arb-cap/trigger011/alt_plane.py \
    >/home/louis/captures/trigger011/alt_plane.log 2>&1 &
fi
export PAPER_SECONDS=43200
export PAPER_SYNC="${HOME}/captures/paper_orbit/sync_state006.bin"
nohup /home/louis/arb-feed/scripts/paper_orbit.sh \
  >/home/louis/captures/paper_orbit/paper_trig011.log 2>&1 &
sleep 2
pgrep -a -f '/home/louis/arb-feed/build/paper_orbit' || true
pgrep -a -f 'alt_plane.py' || true
pgrep -a -f oneshot_live || true
ls /home/louis/arb-cap/oneshot/DISARMED
grep TRIGGER-011 /home/louis/captures/paper_orbit/paper_trig011.log | tail -n 2 || true
