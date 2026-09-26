#!/usr/bin/env python3
"""Locate the trigger signature inside stored tx bytes."""
import json
import hist_funnel as h

rows = []
for line in h.RACES.read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if r.get("supported") and r.get("route") == "Meteora DLMM → Pump Swap":
        rows.append(r)
h.attach_hex(rows)

def b58d(s):
    alph = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in s:
        n = n * 58 + alph.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    raw = b"\x00" * pad + raw
    return raw[-64:] if len(raw) >= 64 else raw.rjust(64, b"\x00")

off_counts = {}
missing = 0
for r in rows:
    raw = bytes.fromhex(r["trigger_tx_hex"])
    sig = b58d(r["trigger_sig"])
    i = raw.find(sig)
    if i < 0:
        missing += 1
        continue
    off_counts[i] = off_counts.get(i, 0) + 1
print("sig offset counts", off_counts, "missing", missing)

# For offset!=1, show 4 bytes before the sig and whether frame_try at sig-1 or sig-2 works
shown = 0
for r in sorted(rows, key=lambda x: -x["profit"]):
    raw = bytes.fromhex(r["trigger_tx_hex"])
    sig = b58d(r["trigger_sig"])
    i = raw.find(sig)
    if i < 0:
        print("MISSING", r["profit"], r["trigger_sig"][:12], "head", raw[:12].hex())
        shown += 1
        if shown >= 4:
            break
        continue
    if i == 1:
        continue
    pre = raw[max(0, i-3):i].hex()
    print(f"off={i} pre={pre} profit={r['profit']:.2f} klass0={h.parse_tx(raw)['why']}")
    shown += 1
    if shown >= 8:
        break
