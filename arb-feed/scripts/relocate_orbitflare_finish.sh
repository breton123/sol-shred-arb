#!/usr/bin/env bash
set -eu
SRC=/home/louis/captures/orbitflare
DST=/data/bsc/captures/orbitflare

kill -9 2664035 2>/dev/null || true
pkill -9 -f 'feed_live --prefix orbitflare' 2>/dev/null || true
sleep 1
pgrep -a feed_live || echo feed_stopped

if [ -d "${SRC}" ] && [ ! -L "${SRC}" ]; then
  rsync -a --remove-source-files "${SRC}/" "${DST}/"
  find "${SRC}" -mindepth 1 -delete || true
  rmdir "${SRC}" || true
fi
ln -sfn "${DST}" /home/louis/captures/orbitflare
ls -ld /home/louis/captures/orbitflare
df -h / /data/bsc
echo FINISH_OK
