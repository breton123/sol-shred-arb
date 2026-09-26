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


def skip_msg(p, off, nsig, versioned_flag):
    if versioned_flag:
        if off >= len(p):
            raise ValueError("veof")
        if p[off] & 0x80:
            if (p[off] & 0x7F) != 0:
                raise ValueError("ver")
            off += 1
            if off >= len(p) or p[off] != nsig:
                raise ValueError("nsig2")
            off += 1
        # else: packed v0, header starts immediately
    else:
        if p[off] != nsig:
            raise ValueError("legacy")
        off += 1
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
    if versioned_flag:
        nlut, off = cu16(p, off)
        for _ in range(nlut):
            off += 32
            nw, off = cu16(p, off)
            off += nw
            nr, off = cu16(p, off)
            off += nr
    return off


def skip_tx(p, off):
    b0 = p[off]
    if b0 & 0x80 and (b0 & 0x7F) != 0 and (b0 & 0x7F) <= 64:
        nsig = b0 & 0x7F
        off += 1
        off += nsig * 64
        return skip_msg(p, off, nsig, True)
    nsig, off = cu16(p, off)
    if nsig == 0 or nsig > 64:
        raise ValueError("nsig_%d" % nsig)
    off += nsig * 64
    versioned = off < len(p) and (p[off] & 0x80) != 0
    return skip_msg(p, off, nsig, versioned)


def parse(buf):
    nent = struct.unpack_from("<Q", buf, 0)[0]
    off = 8
    txs = 0
    for _ in range(nent):
        ntx = struct.unpack_from("<Q", buf, off + 40)[0]
        off += 48
        for _t in range(ntx):
            off = skip_tx(buf, off)
            txs += 1
    return txs


def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        f.read(40)
        cur = None
        recs = []
        ok = fail = 0
        while ok + fail < 400:
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
                recs.sort(key=lambda x: x[0])
                run = []
                for idx, fl, pay in recs:
                    run.append(pay)
                    if fl & 0x80:
                        buf = b"".join(run)
                        try:
                            parse(buf)
                            ok += 1
                        except Exception:
                            fail += 1
                        run = []
                recs = []
                cur = slot
            recs.append((index, flags, p[88:size]))
    print("ok", ok, "fail", fail, "pct", 100.0 * ok / max(1, ok + fail))


if __name__ == "__main__":
    main()
