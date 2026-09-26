#!/usr/bin/env python3
"""Try several skip_tx encodings on slot 449848546 only."""
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


def skip_body(p, off, nsig, versioned):
    if versioned:
        if p[off] & 0x80:
            off += 1
            if p[off] != nsig:
                raise ValueError("nsig2")
            off += 1
    else:
        if p[off] != nsig:
            raise ValueError("leg")
        off += 1
    off += 2
    nkeys, off = cu16(p, off)
    if nkeys > 1024:
        raise ValueError("nkeys")
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


def skip_classic(p, off):
    nsig, off = cu16(p, off)
    if nsig == 0 or nsig > 64:
        raise ValueError("nsig")
    off += nsig * 64
    return skip_body(p, off, nsig, p[off] & 0x80)


def skip_pack_nsig(p, off):
    b0 = p[off]
    if b0 & 0x80 and 1 <= (b0 & 0x7F) <= 64:
        nsig = b0 & 0x7F
        off += 1
        off += nsig * 64
        return skip_body(p, off, nsig, True)
    return skip_classic(p, off)


def skip_tag81(p, off):
    b0 = p[off]
    if b0 == 0x81:
        off += 1
        nsig, off = cu16(p, off)
        if nsig == 0 or nsig > 64:
            raise ValueError("nsig")
        off += nsig * 64
        return skip_body(p, off, nsig, True)
    return skip_classic(p, off)


def skip_tag81_nosig2(p, off):
    b0 = p[off]
    if b0 == 0x81:
        off += 1
        nsig, off = cu16(p, off)
        off += nsig * 64
        # message header without 0x80
        if p[off] != nsig:
            raise ValueError("hdr")
        return skip_body(p, off, nsig, True)
    return skip_classic(p, off)


def run_skip(skip, buf):
    nent = struct.unpack_from("<Q", buf, 0)[0]
    off = 8
    txs = 0
    for e in range(nent):
        ntx = struct.unpack_from("<Q", buf, off + 40)[0]
        off += 48
        for t in range(ntx):
            off = skip(buf, off)
            txs += 1
    return txs


def load_slot(path, want):
    with open(path, "rb") as f:
        f.read(40)
        cur = None
        recs = []
        while True:
            rec = f.read(24)
            if len(rec) < 24:
                return None
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
                            return b"".join(run)
                recs = []
                cur = slot
            recs.append((index, flags, p[88:size]))


def main():
    buf = load_slot(sys.argv[1], int(sys.argv[2]))
    print("len", len(buf))
    for name, fn in (
        ("classic", skip_classic),
        ("pack_nsig", skip_pack_nsig),
        ("tag81", skip_tag81),
        ("tag81_nosig2", skip_tag81_nosig2),
    ):
        try:
            print(name, "OK txs", run_skip(fn, buf))
        except Exception as e:
            print(name, "FAIL", e)


if __name__ == "__main__":
    main()
