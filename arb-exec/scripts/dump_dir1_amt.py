#!/usr/bin/env python3
import json
import struct
from pathlib import Path
p = Path("/home/louis/arb-cap/exec_live002b/signed.tx")
tx = p.read_bytes()
print("len", len(tx))
for off in (545, 547, 549, 546, 548):
    if off + 8 <= len(tx):
        print(f"  u64@{off}", struct.unpack_from("<Q", tx, off)[0], "b", tx[off:off+8].hex())
print("dir546", tx[546], "dir548", tx[548] if len(tx) > 548 else None)
print("disc536", tx[536:544], "disc538", tx[538:546], "disc540", tx[540:548])
alt = Path("/home/louis/arb-exec/.deploy/alt.json")
if alt.exists():
    print("alt.json", alt.read_text().strip())
