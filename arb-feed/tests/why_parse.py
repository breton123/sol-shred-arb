#!/usr/bin/env python3
import struct
import sys
from collections import Counter

DATA = {0xA0, 0x80, 0x90, 0xB0}


def cu16(p, off):
    if off >= len(p):
        raise ValueError("cu16_eof")
    b0 = p[off]
    if b0 < 0x80:
        return b0, off + 1
    if off + 1 >= len(p):
        raise ValueError("cu16_eof")
    b1 = p[off + 1]
    if b1 < 0x80:
        return (b0 & 0x7F) | (b1 << 7), off + 2
    if off + 2 >= len(p):
        raise ValueError("cu16_eof")
    b2 = p[off + 2]
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


def skip_tx(p, off):
    nsig, off = cu16(p, off)
    if nsig == 0 or nsig > 128:
        raise ValueError("nsig_%d" % nsig)
    off += nsig * 64
    if off >= len(p):
        raise ValueError("sig_eof")
    b0 = p[off]
    off += 1
    versioned = False
    if b0 & 0x80:
        if (b0 & 0x7F) != 0:
            raise ValueError("ver_%d" % (b0 & 0x7F))
        if off >= len(p):
            raise ValueError("ver_eof")
        if p[off] != nsig:
            raise ValueError("nsig2_%d_%d" % (p[off], nsig))
        off += 1
        versioned = True
    elif b0 != nsig:
        raise ValueError("legacy_nsig_%d_%d" % (b0, nsig))
    if off + 2 > len(p):
        raise ValueError("hdr_eof")
    off += 2
    nkeys, off = cu16(p, off)
    if nkeys == 0 or nkeys > 2048:
        raise ValueError("nkeys_%d" % nkeys)
    if off + nkeys * 32 + 32 > len(p):
        raise ValueError("keys_eof")
    off += nkeys * 32 + 32
    ninstr, off = cu16(p, off)
    if ninstr > 2048:
        raise ValueError("ninstr_%d" % ninstr)
    for _ in range(ninstr):
        if off >= len(p):
            raise ValueError("ix_eof")
        off += 1
        nacc, off = cu16(p, off)
        off += nacc
        dlen, off = cu16(p, off)
        off += dlen
        if off > len(p):
            raise ValueError("ixdata_eof")
    if versioned:
        nlut, off = cu16(p, off)
        if nlut > 256:
            raise ValueError("nlut_%d" % nlut)
        for _ in range(nlut):
            if off + 32 > len(p):
                raise ValueError("lut_eof")
            off += 32
            nw, off = cu16(p, off)
            off += nw
            nr, off = cu16(p, off)
            off += nr
            if off > len(p):
                raise ValueError("lutidx_eof")
    return off


def parse(buf):
    nent = struct.unpack_from("<Q", buf, 0)[0]
    if nent == 0 or nent > 4096:
        raise ValueError("nent_%d" % nent)
    off = 8
    txs = 0
    for _ in range(nent):
        if off + 48 > len(buf):
            raise ValueError("entry_eof")
        ntx = struct.unpack_from("<Q", buf, off + 40)[0]
        off += 48
        if ntx > 4096:
            raise ValueError("ntx_%d" % ntx)
        for _t in range(ntx):
            off = skip_tx(buf, off)
            txs += 1
    return txs


def main():
    path = sys.argv[1]
    max_slots = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    with open(path, "rb") as f:
        f.read(40)
        cur = None
        recs = []
        why = Counter()
        ok = fail = 0
        while ok + fail < max_slots:
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
                # batches by complete flag
                run = []
                for idx, fl, pay in recs:
                    run.append(pay)
                    if fl & 0x80:
                        buf = b"".join(run)
                        try:
                            parse(buf)
                            ok += 1
                        except Exception as e:
                            fail += 1
                            why[str(e).split("_")[0] if False else str(e).rsplit("_", 1)[0] if str(e)[-1].isdigit() else str(e)] += 1
                            why[str(e)] += 1
                        run = []
                recs = []
                cur = slot
                if ok + fail >= max_slots:
                    break
            recs.append((index, flags, p[88:size]))
    print("ok", ok, "fail", fail)
    for k, v in why.most_common(20):
        print("%6d %s" % (v, k))


if __name__ == "__main__":
    main()
