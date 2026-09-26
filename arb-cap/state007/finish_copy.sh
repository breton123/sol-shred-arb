#!/bin/bash
python3 /home/louis/arb-cap/state005/crlf.py /tmp/s007/STATE007.md /tmp/s007/config.py
cp /tmp/s007/STATE007.md /home/louis/arb-cap/state007/STATE007.md
cp /tmp/s007/config.py /home/louis/arb-state/shyft/config.py
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED=yes; else echo ARMED=no; fi
grep FUNDED /home/louis/arb-exec/scripts/run_oneshot.sh
pgrep -af "state007.py|build/paper_orbit|state005/state006.py" | grep -v grep || true
