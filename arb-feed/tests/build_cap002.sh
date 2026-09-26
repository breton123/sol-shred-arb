#!/bin/bash
set -euo pipefail
sed -i 's/\r$//' /tmp/cap002.c /tmp/CMakeLists.txt
cp /tmp/cap002.c /home/louis/arb-feed/src/cap002.c
cp /tmp/CMakeLists.txt /home/louis/arb-feed/CMakeLists.txt
cd /home/louis/arb-feed
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target cap002 -j
echo build_ok
