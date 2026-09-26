#!/usr/bin/env bash
# One-shot: stop feed_live, move OrbitFlare caps onto /data/bsc, symlink old path.
set -euo pipefail

SRC=/home/louis/captures/orbitflare
DST=/data/bsc/captures/orbitflare
FEED_PAT='feed_live --prefix orbitflare'

mkdir -p "${DST}"

python3 - <<'PY'
from pathlib import Path
p = Path("/data/bsc/captures/soak_fastsoak_20260925/README.txt")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(
    "frozen_at=2026-09-26T10:23Z\n"
    "associated=16469\n"
    "bitexact=8959\n"
    "pump=245/4259\n"
    "dlmm=8714/12210\n"
    "note=METRICS empty ENOSPC; last live score from reconnect stall\n"
)
print("README", p, "bytes", p.stat().st_size)
PY

if pgrep -f "${FEED_PAT}" >/dev/null; then
  echo "STOP feed_live"
  pkill -f "${FEED_PAT}" || true
  sleep 2
fi
pgrep -a feed_live || echo "feed_stopped"

if [[ -d "${SRC}" && ! -L "${SRC}" ]]; then
  echo "MOVE ${SRC} -> ${DST}"
  rsync -a --remove-source-files --info=stats2 "${SRC}/" "${DST}/"
  find "${SRC}" -mindepth 1 -delete
  rmdir "${SRC}"
fi

ln -sfn "${DST}" /home/louis/captures/orbitflare
echo "LINK $(ls -ld /home/louis/captures/orbitflare)"
df -h / /data/bsc
echo "RELOCATE_OK"
