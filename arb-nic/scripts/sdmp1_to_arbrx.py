#!/usr/bin/env python3
"""SDMP1 payload dump → ARBRX1 length-prefixed shred packets.

Frankfurt shred-partial wrote payload only (slot/index/fec/flags + bytes).
We rebuild a data-shred UDP payload so replay_rx / hot_rx see packet
boundaries and a parseable common header. Signature is zeros. Variant is
merkle chained data (0x90). Version 500.
"""

from __future__ import annotations

import argparse
import struct
import sys

SDMP1_MAGIC = b"SDMP1\x00\x00\x00"
ARBRX_MAGIC = b"ARBRX1\x00\x00"
VARIANT = 0x90
VERSION = 500
DATA_HDR = 88
SHRED_MAX = 1228


def convert(src: str, dst: str, limit: int | None) -> int:
    with open(src, "rb") as inf:
        magic = inf.read(8)
        if magic != SDMP1_MAGIC:
            raise SystemExit(f"{src}: not SDMP1 (got {magic!r})")
        n = 0
        skipped = 0
        with open(dst, "wb") as out:
            out.write(ARBRX_MAGIC)
            while True:
                hdr = inf.read(8 + 4 + 4 + 1 + 2)
                if not hdr:
                    break
                if len(hdr) != 19:
                    raise SystemExit(f"{src}: truncated header after {n} records")
                slot, index, fec, flags, plen = struct.unpack_from("<QIIBH", hdr)
                payload = inf.read(plen)
                if len(payload) != plen:
                    raise SystemExit(f"{src}: truncated payload after {n} records")
                size = DATA_HDR + plen
                if size > SHRED_MAX:
                    skipped += 1
                    continue
                pkt = bytearray(size)
                pkt[64] = VARIANT
                struct.pack_into("<Q", pkt, 65, slot)
                struct.pack_into("<I", pkt, 73, index)
                struct.pack_into("<H", pkt, 77, VERSION)
                struct.pack_into("<I", pkt, 79, fec)
                struct.pack_into("<H", pkt, 83, 1)
                pkt[85] = flags
                struct.pack_into("<H", pkt, 86, size)
                pkt[88:] = payload
                out.write(struct.pack("<H", size))
                out.write(pkt)
                n += 1
                if limit is not None and n >= limit:
                    break
    print(f"wrote {n} packets → {dst}  skipped {skipped}", file=sys.stderr)
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    n = convert(args.src, args.dst, args.limit)
    if n == 0:
        raise SystemExit("no packets")


if __name__ == "__main__":
    main()
