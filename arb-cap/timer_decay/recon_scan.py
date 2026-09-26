#!/usr/bin/env python3
"""Inventory recon.bin AUTH span. Read-only."""
from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

MAGIC = 0x36305453
AUTH, INV, PLANE = 3, 4, 5
HDR = 8
FIXED = 80


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/louis/captures/paper_orbit/recon.bin")
    data = path.read_bytes()
    print("size", len(data))
    magic, ver, _ = struct.unpack_from("<IHH", data, 0)
    print("magic", hex(magic), "ver", ver)
    off = HDR
    kinds = Counter()
    protos = Counter()
    n = 0
    first_slot = last_slot = None
    first_now = last_now = None
    max_idx = 0
    auth_n = 0
    while off + 4 <= len(data):
        (ln,) = struct.unpack_from("<I", data, off)
        off += 4
        if ln < FIXED or off + ln > len(data):
            print("trunc at", off, "ln", ln)
            break
        kind, proto, _pad, idx = struct.unpack_from("<BBHI", data, off)
        slot = struct.unpack_from("<Q", data, off + 72)[0]
        body = data[off + FIXED:off + ln]
        off += ln
        kinds[kind] += 1
        n += 1
        if kind == AUTH:
            auth_n += 1
            protos[proto] += 1
            max_idx = max(max_idx, idx)
            if first_slot is None:
                first_slot = slot
            last_slot = slot
            if proto == 1 and len(body) >= 71:
                now = struct.unpack_from("<q", body, 63)[0]
                if first_now is None:
                    first_now = now
                last_now = now
    print("recs", n, "auth", auth_n, "kinds", kinds, "protos", protos)
    print("slot", first_slot, last_slot, "dslot", (last_slot or 0) - (first_slot or 0))
    print("now", first_now, last_now, "dh", ((last_now or 0) - (first_now or 0)) / 3600)
    print("max_idx", max_idx)


if __name__ == "__main__":
    main()
