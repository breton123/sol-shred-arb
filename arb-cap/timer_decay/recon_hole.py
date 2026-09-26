#!/usr/bin/env python3
import struct
from pathlib import Path
p = Path("/home/louis/captures/paper_orbit/recon.bin")
data = p.read_bytes()
print("size", len(data))
off = 8
last_good = 8
n = 0
while off + 4 <= len(data):
    ln = struct.unpack_from("<I", data, off)[0]
    if ln < 80 or ln > 5000 or off + 4 + ln > len(data):
        print("break at", off, "ln", ln, "after", n, "recs")
        last_good = off
        break
    off += 4 + ln
    n += 1
# scan forward for magic or plausible ln
hits = 0
for i in range(last_good, min(last_good + 5_000_000, len(data) - 4)):
    ln = struct.unpack_from("<I", data, i)[0]
    if 80 <= ln <= 2200 and i + 4 + ln <= len(data):
        kind = data[i + 4]
        if kind in (1, 2, 3, 4, 5):
            hits += 1
            if hits <= 5:
                print("resume candidate", i, "ln", ln, "kind", kind)
            if hits == 1:
                # try walk from here
                o = i
                ok = 0
                while o + 4 <= len(data):
                    ln2 = struct.unpack_from("<I", data, o)[0]
                    if ln2 < 80 or ln2 > 5000 or o + 4 + ln2 > len(data):
                        break
                    if data[o + 4] not in (1, 2, 3, 4, 5):
                        break
                    o += 4 + ln2
                    ok += 1
                print("walk from", i, "ok", ok, "end", o)
print("nonzero after hole", sum(1 for b in data[last_good:last_good+10000] if b))
print("tail nonzero", sum(1 for b in data[-10000:] if b))
