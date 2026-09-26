#!/bin/bash
set -euo pipefail
sed -i 's/\r$//' /home/louis/arb-state/shyft/start_fastsoak.sh \
  /home/louis/arb-state/shyft/*.py \
  /home/louis/arb-core/src/state_apply.c \
  /home/louis/arb-core/src/swapix.c \
  /home/louis/arb-core/include/swapix.h
chmod +x /home/louis/arb-state/shyft/start_fastsoak.sh
echo PAPER_BEFORE="$(pgrep -a paper_orbit || true)"
cd /home/louis/arb-core/build
cmake -DCMAKE_BUILD_TYPE=Release .. >/tmp/cmake_fs.log 2>&1
cmake --build . --target state_apply -j
test -x /home/louis/arb-core/build/state_apply
echo APPLY_BUILT
/home/louis/arb-state/shyft/start_fastsoak.sh
echo PAPER_AFTER="$(pgrep -a paper_orbit || true)"
