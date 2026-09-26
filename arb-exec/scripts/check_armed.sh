#!/bin/bash
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_ABSENT; fi
if test -e /home/louis/arb-cap/oneshot/DISARMED; then echo DISARMED; cat /home/louis/arb-cap/oneshot/DISARMED; fi
pgrep -af oneshot_live.py | grep -v grep || echo oneshot_absent
echo "READY=$(test -f /home/louis/captures/state007/READY && echo yes || echo no)"
tail -n 8 /home/louis/arb-cap/oneshot/oneshot6.log
