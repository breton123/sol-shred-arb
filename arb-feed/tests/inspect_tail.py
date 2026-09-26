#!/usr/bin/env python3
"""Sample mid-file and near-end of a growing FEEDCAP1. Read-only."""
import os
import struct
import sys

DATA = {0xA0, 0x80, 0x90, 0xB0}
CODE = {0x50, 0x40, 0x60, 0x70}


def parse_rec(f):
    rec = f.read(24)
    if len(rec) < 24:
        return None
    rx_ns, rx_tsc, ln, seq = struct.unpack("<QQII", rec)
    if ln == 0 or ln > 2048:
        return False
    payload = f.read(ln)
    if len(payload) < ln:
        return None
    return rx_ns, rx_tsc, ln, seq, payload


def walk(f, n, label):
    bad = shred = data_n = code_n = gap = 0
    prev = None
    slots = []
    vers = set()
    ns0 = ns1 = None
    first_seq = last_seq = None
    got = 0
    while got < n:
        rec = parse_rec(f)
        if rec is None:
            break
        if rec is False:
            bad += 1
            got += 1
            continue
        rx_ns, rx_tsc, ln, seq, payload = rec
        got += 1
        if first_seq is None:
            first_seq = seq
            ns0 = rx_ns
        last_seq = seq
        ns1 = rx_ns
        if prev is not None and seq != prev + 1:
            gap += 1
        prev = seq
        if len(payload) >= 83:
            typ = payload[64] & 0xF0
            if typ in DATA or typ in CODE:
                shred += 1
                slots.append(struct.unpack_from("<Q", payload, 65)[0])
                vers.add(struct.unpack_from("<H", payload, 77)[0])
                if typ in DATA:
                    data_n += 1
                else:
                    code_n += 1
            else:
                bad += 1
        else:
            bad += 1
    span = (ns1 - ns0) / 1e6 if ns0 and ns1 else 0
    slot_s = "n/a"
    if slots:
        slot_s = "%d..%d vers=%s" % (min(slots), max(slots), sorted(vers))
    print("%s  n=%d seq=%s..%s gaps=%d shred=%d data=%d coding=%d bad=%d span_ms=%.1f slot=%s"
          % (label, got, first_seq, last_seq, gap, shred, data_n, code_n, bad, span, slot_s))
    return got, bad, gap


def resync(f, budget=2 * 1024 * 1024):
    start = f.tell()
    buf = f.read(budget)
    for i in range(0, len(buf) - 48):
        ln, seq = struct.unpack_from("<II", buf, i + 16)
        if not (80 <= ln <= 1228):
            continue
        end = i + 24 + ln
        if end + 24 > len(buf):
            continue
        ln2, seq2 = struct.unpack_from("<II", buf, end + 16)
        if seq2 == seq + 1 and 80 <= ln2 <= 1228:
            f.seek(start + i)
            return True
    return False


def main():
    path = sys.argv[1]
    size = os.path.getsize(path)
    print("size  %d" % size)
    with open(path, "rb") as f:
        hdr = f.read(40)
        if hdr[:8] != b"FEEDCAP1":
            print("FAIL header")
            return 1
        walk(f, 250, "head250")
        mid = max(40, size // 2)
        f.seek(mid)
        if not resync(f):
            print("FAIL mid resync")
            return 1
        walk(f, 20000, "mid20k")
        tail = max(40, size - 40 * 1024 * 1024)
        f.seek(tail)
        if not resync(f):
            print("FAIL tail resync")
            return 1
        n, bad, gap = walk(f, 20000, "tail20k")
        ok = n > 1000 and bad < n * 0.01 and gap == 0
        print("TAIL   %s" % ("ok" if ok else "WARN"))
        return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
