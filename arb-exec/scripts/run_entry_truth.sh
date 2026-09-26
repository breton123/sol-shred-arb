#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/entry_truth.c /tmp/CMakeLists_feed.txt /tmp/entry_truth.py
cp /tmp/entry_truth.c /home/louis/arb-feed/src/entry_truth.c
# Only splice the entry_truth target if missing — do not clobber remote CMake.
if ! grep -q 'add_executable(entry_truth' /home/louis/arb-feed/CMakeLists.txt; then
  python3 - <<'PY'
from pathlib import Path
p = Path("/home/louis/arb-feed/CMakeLists.txt")
t = p.read_text()
old = "add_executable(cap002 src/cap002.c $<TARGET_OBJECTS:feed>)\ntarget_link_libraries(cap002 pthread)\n"
new = old + "\nadd_executable(entry_truth src/entry_truth.c $<TARGET_OBJECTS:feed>)\ntarget_link_libraries(entry_truth pthread)\n"
if old not in t:
    raise SystemExit("cmake splice failed")
p.write_text(t.replace(old, new, 1))
print("cmake spliced")
PY
fi
cp /tmp/entry_truth.py /home/louis/arb-exec/scripts/entry_truth.py
cd /home/louis/arb-feed/build
cmake --build . --target entry_truth -j
python3 /home/louis/arb-exec/scripts/entry_truth.py
