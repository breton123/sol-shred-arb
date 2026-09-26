#!/usr/bin/env python3
import struct
import sys

DATA = {0xA0, 0x80, 0x90, 0xB0}


def cu16(p, off):
    b0 = p[off]
    if b0 < 0x80:
        return b0, off + 1
    b1 = p[off + 1]
    if b1 < 0x80:
        return (b0 & 0x7F) | (b1 << 7), off + 2
    b2 = p[off + 2]
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


def skip_tx(p, off):
    nsig, off = cu16(p, off)
    if nsig == 0 or nsig > 128:
        raise ValueError("nsig_%d" % nsig)
    off += nsig * 64
    b0 = p[off]
    off += 1
    versioned = False
    if b0 & 0x80:
        if (b0 & 0x7F) != 0:
            raise ValueError("ver")
        if p[off] != nsig:
            raise ValueError("nsig2")
        off += 1
        versioned = True
    elif b0 != nsig:
        raise ValueError("legacy_nsig")
    off += 2
    nkeys, off = cu16(p, off)
    off += nkeys * 32 + 32
    ninstr, off = cu16(p, off)
    for _ in range(ninstr):
        off += 1
        nacc, off = cu16(p, off)
        off += nacc
        dlen, off = cu16(p, off)
        off += dlen
    if versioned:
        nlut, off = cu16(p, off)
        for _ in range(nlut):
            off += 32
            nw, off = cu16(p, off)
            off += nw
            nr, off = cu16(p, off)
            off += nr
    return off


def main():
    path, want = sys.argv[1], int(sys.argv[2])
    with open(path, "rb") as f:
        f.read(40)
        cur = None
        recs = []
        while True:
            rec = f.read(24)
            if len(rec) < 24:
                break
            ln = struct.unpack_from("<I", rec, 16)[0]
            p = f.read(ln)
            if ln < 88 or (p[64] & 0xF0) not in DATA:
                continue
            slot = struct.unpack_from("<Q", p, 65)[0]
            index = struct.unpack_from("<I", p, 73)[0]
            flags = p[85]
            size = struct.unpack_from("<H", p, 86)[0]
            if size < 88 or size > ln:
                continue
            if cur is None:
                cur = slot
            if slot != cur:
                if cur == want:
                    recs.sort(key=lambda x: x[0])
                    run = []
                    for idx, fl, pay in recs:
                        run.append(pay)
                        if fl & 0x80:
                            buf = b"".join(run)
                            nent = struct.unpack_from("<Q", buf, 0)[0]
                            print("batch nent", nent, "len", len(buf))
                            off = 8
                            for e in range(nent):
                                ntx = struct.unpack_from("<Q", buf, off + 40)[0]
                                off += 48
                                for t in range(ntx):
                                    before = off
                                    try:
                                        off = skip_tx(buf, off)
                                    except Exception as err:
                                        print("FAIL e", e, "t", t, "ntx", ntx, "off", before, err)
                                        print("hex", buf[before : before + 64].hex())
                                        print("prev", buf[before - 80 : before].hex())
                                        return
                            print("parsed ok")
                            return
                recs = []
                cur = slot
            recs.append((index, flags, p[88:size]))


if __name__ == "__main__":
    main()
