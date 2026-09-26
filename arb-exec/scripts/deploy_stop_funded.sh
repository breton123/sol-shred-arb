#!/bin/bash
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/paper_orbit.c \
  /tmp/oneshot_live.py \
  /tmp/trigger_outcomes.py \
  /tmp/inspect_ghost_n.py \
  /tmp/run_oneshot.sh \
  /tmp/restart_paper_keep.sh \
  /tmp/COST.json \
  /tmp/COOLDOWN.json
cp /tmp/paper_orbit.c /home/louis/arb-feed/src/paper_orbit.c
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/trigger_outcomes.py /home/louis/arb-exec/scripts/trigger_outcomes.py
cp /tmp/inspect_ghost_n.py /home/louis/arb-exec/scripts/inspect_ghost_n.py
cp /tmp/run_oneshot.sh /home/louis/arb-exec/scripts/run_oneshot.sh
cp /tmp/restart_paper_keep.sh /home/louis/arb-cap/state005/restart_paper_keep.sh
cp /tmp/COST.json /home/louis/arb-cap/oneshot/COST.json
if [[ ! -f /home/louis/arb-cap/oneshot/COOLDOWN.json ]]; then
  cp /tmp/COOLDOWN.json /home/louis/arb-cap/oneshot/COOLDOWN.json
else
  python3 - <<'PY'
import json
from pathlib import Path
cur = Path("/home/louis/arb-cap/oneshot/COOLDOWN.json")
seed = json.loads(Path("/tmp/COOLDOWN.json").read_text())
try:
    obj = json.loads(cur.read_text())
except Exception:
    obj = {"routes": {}}
routes = obj.setdefault("routes", {})
for k, v in (seed.get("routes") or {}).items():
    row = routes.get(k) or {}
    row["trigger_missing"] = max(int(row.get("trigger_missing") or 0), int(v.get("trigger_missing") or 0))
    if v.get("SEND_BLOCKED") or row["trigger_missing"] >= 3:
        row["SEND_BLOCKED"] = True
        row["why"] = v.get("why") or row.get("why") or "TRIGGER_MISSING x3"
    routes[k] = row
cur.write_text(json.dumps(obj, indent=2) + "\n")
print("cooldown", json.dumps(obj))
PY
fi
chmod +x /home/louis/arb-cap/state005/restart_paper_keep.sh \
  /home/louis/arb-exec/scripts/run_oneshot.sh \
  /home/louis/arb-exec/scripts/inspect_ghost_n.py \
  /home/louis/arb-exec/scripts/trigger_outcomes.py
rm -f /home/louis/arb-cap/oneshot/ARMED
python3 - <<'PY'
import os, signal
needles = [b"scripts/oneshot_live.py", b"scripts/trigger_outcomes.py"]
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if any(n in cmd for n in needles):
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid, cmd[:80])
PY
echo "oneshot SEND=0 check:"
FUNDED=0 python3 /home/louis/arb-exec/scripts/oneshot_live.py
echo "=== inspect ghost N ==="
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
python3 /home/louis/arb-exec/scripts/inspect_ghost_n.py
echo "=== restart paper keep journals ==="
bash /home/louis/arb-cap/state005/restart_paper_keep.sh
echo "=== start trigger outcomes ==="
if [[ ! -f /home/louis/arb-cap/oneshot/trigger_outcomes.jsonl ]]; then
  : > /home/louis/arb-cap/oneshot/trigger_outcomes.jsonl
fi
nohup python3 /home/louis/arb-exec/scripts/trigger_outcomes.py \
  >> /home/louis/arb-cap/oneshot/trigger_outcomes.log 2>&1 &
echo "trigger_outcomes pid $!"
sleep 2
pgrep -af paper_orbit || true
pgrep -c feed_live || true
python3 - <<'PY'
import os
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\x00", b" ")
    except OSError:
        continue
    if b"trigger_outcomes" in cmd or b"state006.py" in cmd:
        print(pid, cmd.decode("utf-8", "replace")[:160])
PY
echo "=== first send_quote line ==="
python3 - <<'PY'
from pathlib import Path
p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
n = 0
last = None
if p.exists():
    for line in p.open():
        n += 1
        if "send_quote" in line:
            last = line.strip()
print("opp_synced_lines", n)
print("last_send_quote", (last or "")[:300])
PY
echo "=== ghost summary ==="
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/home/louis/arb-cap/oneshot/GHOST_N.json")
if not p.exists():
    print("no GHOST_N.json")
    raise SystemExit(0)
rep = json.loads(p.read_text())
for c in rep.get("cases") or []:
    print(json.dumps({
        "id": c.get("id"),
        "n": (c.get("n") or "")[:20],
        "rpc": (c.get("rpc") or {}).get("rpc"),
        "ours_slot": c.get("ours_slot"),
        "ours_fee": c.get("ours_fee"),
        "block": c.get("block"),
        "fp": c.get("fingerprint"),
        "n_fields": c.get("n_fields"),
        "n_ix": c.get("n_ix"),
        "cap_hits": c.get("cap_hits"),
        "state006": c.get("state006"),
    }, indent=2))
PY
tail -n 20 /home/louis/arb-cap/oneshot/trigger_outcomes.log || true
