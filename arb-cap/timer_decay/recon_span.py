#!/usr/bin/env python3
from __future__ import annotations
import struct
from collections import Counter
from pathlib import Path

MAGIC = 0x36305453
AUTH, INV = 3, 4
FIXED = 80
NOW_LO, NOW_HI = 1_790_300_000, 1_790_400_000


def iter_recs(path: Path):
    data = path.read_bytes()
    off = 8
    while off + 4 <= len(data):
        (ln,) = struct.unpack_from("<I", data, off)
        off += 4
        if ln < FIXED or off + ln > len(data) or ln > 5000:
            break
        kind, proto, _pad, idx = struct.unpack_from("<BBHI", data, off)
        slot = struct.unpack_from("<Q", data, off + 72)[0]
        body = data[off + FIXED:off + ln]
        off += ln
        yield kind, proto, idx, slot, body


def main() -> None:
    path = Path("/home/louis/captures/paper_orbit/recon.bin")
    n = 0
    good = 0
    nows = []
    slots = []
    by_hour = Counter()
    max_idx_by_hour = {}
    for kind, proto, idx, slot, body in iter_recs(path):
        n += 1
        if kind != AUTH or proto != 1 or len(body) < 71:
            continue
        now = struct.unpack_from("<q", body, 63)[0]
        if not (NOW_LO <= now <= NOW_HI):
            continue
        good += 1
        nows.append(now)
        if 400_000_000 < slot < 500_000_000:
            slots.append(slot)
        h = now // 3600
        by_hour[h] += 1
        max_idx_by_hour[h] = max(max_idx_by_hour.get(h, 0), idx)
    print("recs", n, "good_dlmm_auth", good)
    if nows:
        print("now", min(nows), max(nows), "hours", (max(nows) - min(nows)) / 3600)
    if slots:
        print("slot", min(slots), max(slots))
    for h in sorted(by_hour):
        print(f"  hour {h} n={by_hour[h]} max_idx={max_idx_by_hour[h]}")


if __name__ == "__main__":
    main()
