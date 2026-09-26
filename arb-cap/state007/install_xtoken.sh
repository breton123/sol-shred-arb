#!/bin/bash
# Install x-token from /tmp/s007/xtoken.env. Never cat/echo the token.
set -euo pipefail
umask 077
if [[ ! -f /tmp/s007/xtoken.env ]]; then
  echo "missing xtoken.env"
  exit 1
fi
chmod 600 /tmp/s007/xtoken.env
# Keep URL/region; replace token only.
python3 - <<'PY'
from pathlib import Path
src = Path("/tmp/s007/xtoken.env")
dst = Path("/home/louis/.arb-state007.env")
vals = {}
if dst.exists():
    for line in dst.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
for line in src.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip()
vals.setdefault("SHYFT_GRPC_URL", "https://grpc.fra.shyft.to")
vals.setdefault("SHYFT_REGION", "fra")
out = []
for k in ("SHYFT_GRPC_URL", "SHYFT_X_TOKEN", "SHYFT_REGION"):
    if k in vals:
        out.append(f"{k}={vals[k]}")
dst.write_text("\n".join(out) + "\n", encoding="utf-8")
dst.chmod(0o600)
print("installed token_len", len(vals.get("SHYFT_X_TOKEN") or ""))
PY
rm -f /tmp/s007/xtoken.env
# Restart state007 only. FUNDED stays 0. Do not start oneshot.
python3 - <<'PY'
import os, signal
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read()
    except OSError:
        continue
    if b"arb-state/shyft/state007.py" in cmd:
        os.kill(int(pid), signal.SIGTERM)
        print("stopped", pid)
PY
sleep 0.6
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
# shellcheck disable=SC1091
. /home/louis/.arb-state007.env
set +a
nohup python3 /home/louis/arb-state/shyft/state007.py \
  >> /home/louis/captures/state007/state007.log 2>&1 < /dev/null &
echo "state007 $!"
sleep 6
echo "=== log ==="
tail -n 16 /home/louis/captures/state007/state007.log
echo "=== armed ==="
if test -e /home/louis/arb-cap/oneshot/ARMED; then echo ARMED; else echo ARMED_ABSENT; fi
echo "=== probe ==="
python3 /home/louis/arb-state/shyft/probe.py
