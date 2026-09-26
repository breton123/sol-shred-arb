#!/usr/bin/env bash
set -euo pipefail
D=/data/bsc/captures
cp -f "$D/orbitflare.env" "$D/orbitflare_watch.sh" "$D/process_health.py" "$D/process_health.sh" "$D/install_ops_cron.sh" /home/louis/arb-feed/scripts/
cp -f "$D/state008.py" /home/louis/arb-state/shyft/state008.py
cp -f "$D/reduce_soak.py" /data/bsc/captures/soak_fastsoak_20260925/reduce_soak.py
mkdir -p /home/louis/arb-cap/state008
cp -f "$D/reduce_soak.py" /home/louis/arb-cap/state008/reduce_soak.py
sed -i 's/\r$//' /home/louis/arb-feed/scripts/orbitflare.env \
  /home/louis/arb-feed/scripts/orbitflare_watch.sh \
  /home/louis/arb-feed/scripts/process_health.py \
  /home/louis/arb-feed/scripts/process_health.sh \
  /home/louis/arb-feed/scripts/install_ops_cron.sh \
  /home/louis/arb-state/shyft/state008.py \
  /data/bsc/captures/soak_fastsoak_20260925/reduce_soak.py
python3 -m py_compile /home/louis/arb-state/shyft/state008.py
bash /home/louis/arb-feed/scripts/install_ops_cron.sh
echo REDUCE
python3 /data/bsc/captures/soak_fastsoak_20260925/reduce_soak.py \
  /data/bsc/captures/soak_fastsoak_20260925/state008 \
  /data/bsc/captures/soak_fastsoak_20260925
echo ALL_OK
