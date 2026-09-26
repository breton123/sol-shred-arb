#!/bin/bash
# Deploy prepared race path + freshness + racer. Keep journals. Leave feed_live.
set -euo pipefail
python3 /home/louis/arb-cap/state005/crlf.py \
  /tmp/paper_orbit.c \
  /tmp/CMakeLists_feed.txt \
  /tmp/CMakeLists_exec.txt \
  /tmp/oneshot_live.py \
  /tmp/run_oneshot.sh \
  /tmp/start_racer.sh \
  /tmp/restart_paper_keep.sh \
  /tmp/alt_plane.py \
  /tmp/state006.py \
  /tmp/exec_swqos_racer.c
cp /tmp/paper_orbit.c /home/louis/arb-feed/src/paper_orbit.c
cp /tmp/CMakeLists_feed.txt /home/louis/arb-feed/CMakeLists.txt
cp /tmp/CMakeLists_exec.txt /home/louis/arb-exec/CMakeLists.txt
cp /tmp/oneshot_live.py /home/louis/arb-exec/scripts/oneshot_live.py
cp /tmp/run_oneshot.sh /home/louis/arb-exec/scripts/run_oneshot.sh
cp /tmp/start_racer.sh /home/louis/arb-exec/scripts/start_racer.sh
cp /tmp/restart_paper_keep.sh /home/louis/arb-cap/state005/restart_paper_keep.sh
cp /tmp/alt_plane.py /home/louis/arb-exec/scripts/alt_plane.py
cp /tmp/state006.py /home/louis/arb-cap/state005/state006.py
cp /tmp/exec_swqos_racer.c /home/louis/arb-exec/tests/exec_swqos_racer.c
chmod +x /home/louis/arb-exec/scripts/run_oneshot.sh \
  /home/louis/arb-exec/scripts/start_racer.sh \
  /home/louis/arb-cap/state005/restart_paper_keep.sh
if [[ -f /tmp/helius.env ]]; then
  python3 - <<'PY'
from pathlib import Path
src = Path("/tmp/helius.env")
dst = Path("/home/louis/.arb-smoke.env")
kv = {}
for line in src.read_text(encoding="utf-8").splitlines():
    s = line.strip()
    if s.startswith("export "):
        s = s[7:]
    if "=" in s and not s.startswith("#"):
        k, v = s.split("=", 1)
        kv[k.strip()] = v.strip().strip("\"'")
keep = []
if dst.exists():
    for line in dst.read_text(encoding="utf-8").splitlines():
        raw = line[7:] if line.startswith("export ") else line
        k = raw.split("=", 1)[0].strip() if "=" in raw else ""
        if k in kv:
            continue
        keep.append(line)
for k, v in kv.items():
    keep.append(f"export {k}={v}")
dst.write_text("\n".join(keep) + "\n", encoding="utf-8")
dst.chmod(0o600)
print("helius env merged host-only")
PY
  python3 - <<'PY'
import os
from pathlib import Path
from urllib.parse import urlparse
text = Path("/home/louis/.arb-smoke.env").read_text(encoding="utf-8")
os.environ.clear()
for line in text.splitlines():
    s = line[7:] if line.startswith("export ") else line
    if "=" in s and not s.startswith("#"):
        k, v = s.split("=", 1)
        os.environ[k.strip()] = v.strip().strip("\"'")
u = os.environ.get("HELIUS_RPC_URL") or ""
print("rpc_host", urlparse(u).hostname or "missing")
PY
fi
rm -f /home/louis/arb-cap/oneshot/ARMED
python3 - <<'PY'
import os, signal
needles = [b"scripts/oneshot_live.py", b"state006.py"]
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if any(n in cmd for n in needles):
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
echo "=== rebuild paper ==="
bash /home/louis/arb-cap/state005/restart_paper_keep.sh
echo "=== state006 ==="
nohup python3 /home/louis/arb-cap/state005/state006.py \
  >> /home/louis/captures/paper_orbit/state006.log 2>&1 < /dev/null &
echo "state006 pid $!"
echo "=== racer ==="
bash /home/louis/arb-exec/scripts/start_racer.sh
echo "=== plane templates ==="
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
set +a
python3 /home/louis/arb-exec/scripts/alt_plane.py sync
echo "=== arm ONESHOT#6 ==="
nohup bash /home/louis/arb-exec/scripts/run_oneshot.sh \
  >> /home/louis/arb-cap/oneshot/oneshot6.log 2>&1 < /dev/null &
echo "oneshot pid $!"
sleep 3
pgrep -af 'paper_orbit|oneshot_live|exec_swqos_racer|state006' || true
pgrep -c feed_live || true
tail -n 12 /home/louis/arb-cap/oneshot/oneshot6.log || true
tail -n 6 /home/louis/captures/paper_orbit/paper_state006.log || true
