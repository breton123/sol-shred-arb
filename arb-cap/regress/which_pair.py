#!/usr/bin/env python3
"""See which pair file supplied the 21 non-wire triggers, and whether another copy parses."""
import json
import hist_funnel as h

want = "5HRxpP9BoKmxietiDPUBy2F8pNRj9zhWMAx7UzWq9DFnBf9jYH5d7pvwScGLCVXMVGM2ABXv7B4YPp4TgLPTNyw7"
key = '"mriya_sig":"'
for path in h.PAIR_FILES:
    with path.open(encoding="utf-8") as f:
        for line in f:
            i = line.find(key)
            if i < 0:
                continue
            j = line.find('"', i + len(key))
            sig = line[i + len(key):j]
            if sig != want:
                continue
            rec = json.loads(line)
            raw = bytes.fromhex(rec.get("trigger_tx_hex") or "")
            p = h.parse_tx(raw)
            print(path.name, "len", len(raw), "head", raw[:8].hex(), p["klass"], p["why"], "act", rec.get("actionable_ok"), rec.get("actionable_proto"))
            break
        else:
            print(path.name, "MISSING")
