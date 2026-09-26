#!/usr/bin/env python3
"""Read-only check of a growing FEEDCAP1 file. Does not stop the writer."""
import os
import struct
import sys
import time

SHRED_OFF_VARIANT = 64
SHRED_OFF_SLOT = 65
SHRED_OFF_VERSION = 77
DATA = {0xA0, 0x80, 0x90, 0xB0}
CODE = {0x50, 0x40, 0x60, 0x70}


def load_u64(b, off):
    return struct.unpack_from("<Q", b, off)[0]


def load_u16(b, off):
    return struct.unpack_from("<H", b, off)[0]


def inspect(path, limit=30000):
    with open(path, "rb") as f:
        hdr = f.read(40)
        if len(hdr) < 40 or hdr[:8] != b"FEEDCAP1":
            print("FAIL  header")
            return 1
        realtime0, mono0, tsc_hz = struct.unpack_from("<QQQ", hdr, 8)
        print("header  FEEDCAP1  realtime0=%d  mono0=%d  tsc_hz=%d" % (realtime0, mono0, tsc_hz))
        n = 0
        bad = 0
        shred = 0
        data_n = 0
        code_n = 0
        gap = 0
        prev_seq = None
        lens = []
        slots = []
        vers = set()
        tsc0 = None
        ns0 = None
        ns1 = None
        trunc = 0
        while n < limit:
            rec = f.read(24)
            if len(rec) < 24:
                break
            rx_ns, rx_tsc, ln, seq = struct.unpack("<QQII", rec)
            if ln > 2048:
                print("FAIL  len %d at rec %d" % (ln, n))
                return 1
            payload = f.read(ln)
            if len(payload) < ln:
                break
            n += 1
            lens.append(ln)
            if ln == 2048:
                trunc += 1
            if prev_seq is not None and seq != prev_seq + 1:
                gap += 1
            prev_seq = seq
            if tsc0 is None:
                tsc0 = rx_tsc
                ns0 = rx_ns
            ns1 = rx_ns
            if len(payload) >= 83:
                typ = payload[SHRED_OFF_VARIANT] & 0xF0
                if typ in DATA or typ in CODE:
                    shred += 1
                    slots.append(load_u64(payload, SHRED_OFF_SLOT))
                    vers.add(load_u16(payload, SHRED_OFF_VERSION))
                    if typ in DATA:
                        data_n += 1
                    else:
                        code_n += 1
                else:
                    bad += 1
            else:
                bad += 1
        if n == 0:
            print("FAIL  no complete records")
            return 1
        lens.sort()
        print("records  %d  (stopped at sample cap or EOF)" % n)
        print("seq      first=%d last=%d gaps=%d" % (prev_seq - n + 1 if prev_seq is not None else -1, prev_seq, gap))
        print("len      min=%d p50=%d max=%d  eq2048=%d" % (lens[0], lens[n // 2], lens[-1], trunc))
        print("parse    shred=%d data=%d coding=%d bad=%d" % (shred, data_n, code_n, bad))
        print("mono_ns  first=%d last=%d  span_ms=%.1f" % (ns0, ns1, (ns1 - ns0) / 1e6 if ns1 and ns0 else 0))
        if slots:
            print("slot     min=%d max=%d  versions=%s" % (min(slots), max(slots), sorted(vers)))
        ok = shred > n * 0.9 and gap == 0 and trunc == 0 and tsc_hz > 0
        print("SAMPLE  %s" % ("ok" if ok else "WARN"))
        return 0 if ok else 2


def main():
    path = sys.argv[1]
    sz1 = os.path.getsize(path)
    time.sleep(2.0)
    sz2 = os.path.getsize(path)
    print("file    %s" % path)
    print("grow    %d -> %d  (+%d B / 2s)" % (sz1, sz2, sz2 - sz1))
    if sz2 <= sz1:
        print("FAIL  file not growing")
        return 1
    return inspect(path)


if __name__ == "__main__":
    sys.exit(main())
