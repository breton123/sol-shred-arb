#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/oneshot_live.py /tmp/exec_swqos_oneshot.c /tmp/CMakeLists.txt \
  /tmp/run_oneshot.sh /tmp/peek_oneshot.py
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/exec_swqos_oneshot.c /home/louis/arb-exec/tests/exec_swqos_oneshot.c
cp /tmp/CMakeLists.txt /home/louis/arb-exec/CMakeLists.txt
cp /tmp/run_oneshot.sh /home/louis/arb-exec/scripts/run_oneshot.sh
cp /tmp/peek_oneshot.py /tmp/peek_oneshot_ok.py
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
if [[ -f /home/louis/.arb-swqos.env ]]; then
  # shellcheck disable=SC1091
  . /home/louis/.arb-swqos.env
fi
set +a
python3 /tmp/peek_oneshot.py
cd /home/louis/arb-exec
cmake -S . -B build >/tmp/oneshot_cmake.log 2>&1
cmake --build build --target exec_swqos_oneshot
ls -l /home/louis/arb-exec/build/exec_swqos_oneshot
