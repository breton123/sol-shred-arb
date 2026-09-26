#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("/home/louis/arb-cap/oneshot/RESULT.json")
r = json.loads(p.read_text())
fire = r.get("fire") or {}
st = fire.get("status") or {}
print("why", r.get("why"))
print("dir", fire.get("direction"), "send", fire.get("send_lamports"), "est_gp", fire.get("est_gp"))
print("sig", fire.get("sig"))
print("alt", fire.get("alt"))
print("dlmm", fire.get("dlmm"))
print("pump", fire.get("pump"))
print("swqos_rc", fire.get("swqos_rc"), "send_ms", fire.get("send_wall_ms"))
print("status_err", st.get("err"), "conf", st.get("confirmationStatus"))
print("tx_len", fire.get("tx_len"))
