#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/frame.c /tmp/frame.h /tmp/core010.c /tmp/frame_truth.c \
  /tmp/CMakeLists_core.txt /tmp/CMakeLists_feed.txt /tmp/frame_truth.py
cp /tmp/frame.c /home/louis/arb-core/src/frame.c
cp /tmp/frame.h /home/louis/arb-core/include/frame.h
cp /tmp/core010.c /home/louis/arb-core/tests/core010.c
cp /tmp/frame_truth.c /home/louis/arb-feed/src/frame_truth.c
cp /tmp/CMakeLists_core.txt /home/louis/arb-core/CMakeLists.txt
cp /tmp/CMakeLists_feed.txt /home/louis/arb-feed/CMakeLists.txt
cp /tmp/frame_truth.py /home/louis/arb-exec/scripts/frame_truth.py
cd /home/louis/arb-core/build
cmake .. >/tmp/core010_cmake.log
cmake --build . --target core010 -j
./core010
cd /home/louis/arb-feed/build
cmake .. >/tmp/frame_truth_cmake.log
cmake --build . --target frame_truth -j
python3 /home/louis/arb-exec/scripts/frame_truth.py
