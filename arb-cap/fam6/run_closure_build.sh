#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/s007/hot.c /tmp/s007/paper.c /tmp/s007/hot.h /tmp/s007/paper.h \
  /tmp/s007/hot001.c /tmp/s007/dump_closure.c /tmp/s007/CMakeLists.txt \
  /tmp/s007/hops_plane.py /tmp/s007/hops_sim.py /tmp/s007/audit_closure.py
cp /tmp/s007/hot.c /home/louis/arb-core/src/hot.c
cp /tmp/s007/paper.c /home/louis/arb-core/src/paper.c
cp /tmp/s007/hot.h /home/louis/arb-core/include/hot.h
cp /tmp/s007/paper.h /home/louis/arb-core/include/paper.h
cp /tmp/s007/hot001.c /home/louis/arb-core/tests/hot001.c
cp /tmp/s007/dump_closure.c /home/louis/arb-core/tests/dump_closure.c
cp /tmp/s007/CMakeLists.txt /home/louis/arb-core/CMakeLists.txt
cp /tmp/s007/hops_plane.py /home/louis/arb-exec/scripts/hops_plane.py
cp /tmp/s007/hops_sim.py /home/louis/arb-exec/scripts/hops_sim.py
cp /tmp/s007/audit_closure.py /home/louis/arb-exec/scripts/audit_closure.py
mkdir -p /home/louis/arb-cap/fam6
cmake -S /home/louis/arb-core -B /tmp/build-closure -DCMAKE_BUILD_TYPE=Release >/tmp/cmake-closure.log
cmake --build /tmp/build-closure --target route0_orient dump_closure hot001 -j4
/tmp/build-closure/route0_orient
/tmp/build-closure/hot001 /home/louis/captures/paper_orbit/liveuniv.bin
/tmp/build-closure/dump_closure /home/louis/captures/paper_orbit/liveuniv.bin \
  > /home/louis/arb-cap/fam6/ROUTES.json
python3 /home/louis/arb-exec/scripts/hops_plane.py
python3 /home/louis/arb-exec/scripts/hops_sim.py
python3 /home/louis/arb-exec/scripts/audit_closure.py
echo '=== funded untouched ==='
test -e /home/louis/arb-cap/oneshot/ARMED && echo ARMED
ps -p 2712659,2712932,2714353 -o pid,etime,cmd --no-headers || true
