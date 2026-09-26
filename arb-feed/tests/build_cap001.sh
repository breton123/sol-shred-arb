#!/bin/bash
set -euo pipefail
sed -i 's/\r$//' /tmp/cap001.c /tmp/CMakeLists.txt /tmp/README.md
cp /tmp/cap001.c /home/louis/arb-feed/src/cap001.c
cp /tmp/CMakeLists.txt /home/louis/arb-feed/CMakeLists.txt
cp /tmp/README.md /home/louis/arb-feed/README.md
cd /home/louis/arb-feed
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target cap001 -j
ls -la /home/louis/captures > /home/louis/captures/derived/inventory.txt
echo "build ok"
