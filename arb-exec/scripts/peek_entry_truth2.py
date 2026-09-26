#!/usr/bin/env python3
import json
from pathlib import Path

rep = json.loads(Path("/home/louis/arb-cap/oneshot/ENTRY_TRUTH.json").read_text())
print("ENTRY_VALID")
for x in rep["cases"]:
    if x["class"] == "ENTRY_VALID":
        print(json.dumps({
            "outcome": x.get("outcome"),
            "sig": x["sig_hex"][:16],
            "shred": x["shred"],
            "batch_ok": x.get("batch_ok"),
            "tx_i": x.get("tx_i"),
            "batch": [x.get("batch_i0"), x.get("batch_i1")],
            "dt_ns": x.get("dt_ns"),
        }))
print("landed")
for x in rep["cases"]:
    if x.get("outcome") == "landed-success":
        print(x["class"], x["sig_hex"][:16], x.get("shred"), "batch_seen", x.get("batch_seen"), "dt", x.get("dt_ns"))
n4 = "92ecff4c9a09dfa5"
for x in rep["cases"]:
    if x["sig_hex"].startswith(n4):
        print("N4", x["class"], "outcome", x.get("outcome"), "batch_ok", x.get("batch_ok"),
              "entry_hit", x.get("entry_hit"), x.get("shred"), "dt", x.get("dt_ns"))
