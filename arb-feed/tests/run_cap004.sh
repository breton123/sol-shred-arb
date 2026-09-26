#!/bin/bash
set -euo pipefail
sed -i 's/\r$//' /tmp/cap004.c /tmp/CMakeLists.txt
cp /tmp/cap004.c /home/louis/arb-feed/src/cap004.c
cp /tmp/CMakeLists.txt /home/louis/arb-feed/CMakeLists.txt
cd /home/louis/arb-feed
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target cap004 -j
/home/louis/arb-feed/build/cap004 \
  --dir /home/louis/captures \
  --pairs /home/louis/captures/derived/pairs.jsonl \
  --out /home/louis/captures/derived/cap004_hits.jsonl
echo SCAN_OK
wc -l /home/louis/captures/derived/cap004_hits.jsonl
