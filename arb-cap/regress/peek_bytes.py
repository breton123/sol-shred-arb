#!/usr/bin/env python3
import json
from collections import Counter
import hist_funnel as h

rows = []
for line in h.RACES.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r.get("supported") and r.get("route") == "Meteora DLMM → Pump Swap":
        rows.append(r)
h.attach_hex(rows)
print("prefixes")
for r in sorted(rows, key=lambda x: -x["profit"])[:6]:
    raw = bytes.fromhex(r["trigger_tx_hex"])
    parsed = h.parse_tx(raw)
    print(r["profit"], parsed["klass"], parsed["why"], "len", len(raw), "head", raw[:8].hex(), "dlmm", h.PROG_DLMM in raw, "pump", h.PROG_PUMP in raw)

# all nsig=129 heads
heads = Counter()
for r in rows:
    raw = bytes.fromhex(r["trigger_tx_hex"])
    if h.parse_tx(raw)["why"] == "nsig_range":
        heads[raw[:4].hex()] += 1
print("nsig heads", heads)

# no_dex: is there a jupiter/router-looking start, and sig count
print("no_dex heads")
c = Counter()
for r in rows:
    raw = bytes.fromhex(r["trigger_tx_hex"])
    p = h.parse_tx(raw)
    if p["why"] == "no_dex_bytes":
        c[(raw[0], p["nsig"], p["nkeys"], len(raw))] += 1
print(c.most_common(8))
