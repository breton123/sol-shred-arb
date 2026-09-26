#!/bin/bash
set -euo pipefail
set -a
# shellcheck disable=SC1091
. /home/louis/.arb-smoke.env
if [[ -f /home/louis/.arb-swqos.env ]]; then
  # shellcheck disable=SC1091
  . /home/louis/.arb-swqos.env
fi
set +a
echo "paper"
pgrep -af paper_orbit | head -5 || true
echo "feed"
pgrep -af feed_live | head -2 || true
echo "swqos_bin"
ls -l /home/louis/arb-exec/build/exec_swqos /home/louis/arb-exec/swqos/target/release/libswqos_quic.a 2>/dev/null || true
echo "swqos_key" "$(python3 -c 'import os; print(int(bool(os.environ.get("SWQOS_KEY") or os.environ.get("SWQOS_API_KEY"))))')"
echo "audit_lines" "$(wc -l < /home/louis/captures/paper_orbit/opp_synced.jsonl 2>/dev/null || echo 0)"
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path
u = os.environ.get("HELIUS_RPC_URL") or (
    "https://mainnet.helius-rpc.com/?api-key=" + os.environ["HELIUS_API_KEY"]
)
body = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "getBalance",
    "params": ["HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"],
}).encode()
req = urllib.request.Request(u, data=body, headers={"Content-Type": "application/json"})
val = json.loads(urllib.request.urlopen(req, timeout=20).read())["result"]["value"]
print(f"wallet_sol {val/1e9:.6f}")
p = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
if p.exists():
    lines = [x for x in p.read_text().splitlines() if x.strip()]
    print(f"audit_n {len(lines)}")
    for line in lines[-5:]:
        r = json.loads(line)
        a = r.get("arb") or {}
        print(
            f"  last pool={(r.get('pool') or '')[:8]} dir={a.get('direction')} "
            f"ain={a.get('amount_in')} gp={a.get('gross')} auth={r.get('auth_slot')}"
        )
univ = Path("/home/louis/captures/paper_orbit/liveuniv.json")
if univ.exists():
    u = json.loads(univ.read_text())
    print("univ", u.get("gen"), "n", u.get("n"), "keys", list((u.get("pools") or [{}])[0].keys())[:16])
PY
