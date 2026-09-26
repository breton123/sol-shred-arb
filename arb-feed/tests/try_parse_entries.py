#!/usr/bin/env python3
import struct
import sys

DATA = {0xA0, 0x80, 0x90, 0xB0}


def cu16(p, off):
    if off >= len(p):
        raise ValueError("cu16")
    b0 = p[off]
    if b0 < 0x80:
        return b0, off + 1
    if off + 1 >= len(p):
        raise ValueError("cu16")
    b1 = p[off + 1]
    if b1 < 0x80:
        return (b0 & 0x7F) | (b1 << 7), off + 2
    if off + 2 >= len(p):
        raise ValueError("cu16")
    b2 = p[off + 2]
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


def skip_tx(p, off):
    nsig, off = cu16(p, off)
    if nsig == 0 or nsig > 64:
        raise ValueError("nsig %d" % nsig)
    off += nsig * 64
    if off >= len(p):
        raise ValueError("sig")
    b0 = p[off]
    off += 1
    if b0 & 0x80:
        if (b0 & 0x7F) != 0:
            raise ValueError("ver")
        if off >= len(p) or p[off] != nsig:
            raise ValueError("nsig2")
        off += 1
        versioned = True
    else:
        if b0 != nsig:
            raise ValueError("legacy nsig")
        versioned = False
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


def parse_vec_entries(buf, ntx_u64=True):
    if len(buf) < 8:
        return None
    nent = struct.unpack_from("<Q", buf, 0)[0]
    if nent > 4096:
        return None
    off = 8
    entries = 0
    empty = 0
    txs = 0
    for _ in range(nent):
        if off + 40 > len(buf):
            return None
        off += 40
        if ntx_u64:
            if off + 8 > len(buf):
                return None
            ntx = struct.unpack_from("<Q", buf, off)[0]
            off += 8
        else:
            ntx, off = cu16(buf, off)
        if ntx > 4096:
            raise ValueError("ntx %d nent %d" % (ntx, nent))
        entries += 1
        if ntx == 0:
            empty += 1
            continue
        for _t in range(ntx):
            off = skip_tx(buf, off)
            txs += 1
    return nent, entries, empty, txs, off, len(buf) - off


def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        f.read(40)
        by_slot = {}
        ok = fail = 0
        for _ in range(20000):
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
            by_slot.setdefault(slot, []).append((index, flags, p[88:size]))
            if flags & 0x80:
                recs = sorted(by_slot[slot], key=lambda x: x[0])
                # this complete batch only (drop prior completes already parsed)
                buf = b"".join(x[2] for x in recs)
                print("head", buf[:80].hex())
                try:
                    r = parse_vec_entries(buf, True)
                except Exception as e:
                    print("u64", e)
                    try:
                        r = parse_vec_entries(buf, False)
                    except Exception as e2:
                        fail += 1
                        print("FAIL slot", slot, e2)
                        del by_slot[slot]
                        if ok + fail >= 8:
                            break
                        continue
                if r is None:
                    fail += 1
                    print("FAIL slot", slot, "nshred", len(recs), "blen", len(buf))
                else:
                    ok += 1
                    print("OK   slot", slot, "nent", r[0], "txs", r[3], "pad", r[5])
                del by_slot[slot]
                if ok + fail >= 8:
                    break
        print("ok", ok, "fail", fail)


if __name__ == "__main__":
    main()
