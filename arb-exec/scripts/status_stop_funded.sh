#!/bin/bash
set -euo pipefail
echo "=== TRIGGER_TABLE ==="
cat /home/louis/arb-cap/oneshot/TRIGGER_TABLE.json
echo
echo "=== trigger log ==="
tail -n 4 /home/louis/arb-cap/oneshot/trigger_outcomes.log
echo
echo "=== paper ==="
grep "PAPER-ORBIT  up=" /home/louis/captures/paper_orbit/paper_state006.log | tail -n 2
echo
python3 - <<'PY'
from pathlib import Path
p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
n = sq = 0
last = None
for line in p.open():
    n += 1
    if "send_quote" in line:
        sq += 1
        last = line.strip()
print("opp_synced", n, "send_quote", sq)
print((last or "none")[:500])
PY
if [[ -e /home/louis/arb-cap/oneshot/ARMED ]]; then
  echo "ARMED=present"
else
  echo "ARMED=absent"
fi
FUNDED=0 python3 /home/louis/arb-exec/scripts/oneshot_live.py
echo "feed_live $(pgrep -c feed_live || true)"
