#!/bin/bash
echo "=== log ==="
tail -n 12 /home/louis/captures/state007/state007.log
echo "=== plane ==="
python3 -c "import json; print(json.load(open('/home/louis/captures/state007/PLANE.json')))"
echo "=== metrics ==="
python3 -c "import json; d=json.load(open('/home/louis/captures/state007/METRICS.json')); lat=d.get('lat_ns') or {}; print({k:d[k] for k in d if k!='lat_ns'}); print('lat', lat)"
echo "=== compare ==="
if test -f /home/louis/captures/state007/COMPARE.json; then python3 -c "import json; print(json.load(open('/home/louis/captures/state007/COMPARE.json')))"; else echo none; fi
echo "=== funnel ==="
python3 /home/louis/arb-cap/state007/agg_funnel007.py /home/louis/captures/paper_orbit/opp_synced.jsonl 300
echo "=== funded ==="
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_ABSENT; fi
