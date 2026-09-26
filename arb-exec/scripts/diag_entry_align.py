#!/usr/bin/env python3
"""Where does N sit in the reconstructed slot-450394585 byte stream?"""
from __future__ import annotations

import struct
from pathlib import Path

SLOT = 450394585
CAP = Path("/home/louis/captures/orbitflare/orbitflare-20260925-153500.cap")
SIG = bytes.fromhex(
    "92ecff4c9a09dfa5d5ec8795a9348ac66b85149a82668a6dc8e02edb331f04f9"
    "b79b62bba925df403401167dc0266e146151c8969d06c11beedd59e296340580"
)
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
    if nsig == 0 or nsig > 64:
        raise ValueError("nsig %d at %d" % (nsig, off))
    first = p[off:off + 64]
    off += nsig * 64
    b0 = p[off]
    off += 1
    versioned = False
    if b0 & 0x80:
        if (b0 & 0x7F) != 0:
            raise ValueError("ver at %d" % off)
        if p[off] != nsig:
            raise ValueError("nsig2 at %d" % off)
        off += 1
        versioned = True
    elif b0 != nsig:
        raise ValueError("legacy at %d" % off)
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
    return off, first, nsig


def main():
    by_i = {}
    with CAP.open("rb") as f:
        f.seek(40)
        while True:
            rec = f.read(24)
            if len(rec) < 24:
                break
            _rx, _tsc, ln, _seq = struct.unpack("<QQII", rec)
            p = f.read(ln)
            if len(p) < 88 or (p[64] & 0xF0) not in DATA:
                continue
            if struct.unpack_from("<Q", p, 65)[0] != SLOT:
                continue
            idx = struct.unpack_from("<I", p, 73)[0]
            sz = struct.unpack_from("<H", p, 86)[0]
            if 88 <= sz <= ln:
                by_i[idx] = p[88:sz]
    buf = b"".join(by_i[i] for i in sorted(by_i))
    pos = buf.find(SIG)
    print("concat", len(buf), "nshred", len(by_i), "sig_off", pos)
    if pos >= 0:
        pre = buf[max(0, pos - 8):pos]
        print("bytes_before_sig", pre.hex(), "as_cu16_try", pre[-1] if pre else None)
        print("byte_at_pos-1", buf[pos - 1] if pos else None, "pos-2", buf[pos - 2] if pos > 1 else None)
        # is this nsig=1 (0x01) + sig?
        framed = pos > 0 and buf[pos - 1] == 1
        print("looks_like_nsig1_plus_sig", framed)
        # try skip_tx starting at pos-1, pos-2, pos-3
        for back in (1, 2, 3, 0):
            start = pos - back
            if start < 0:
                continue
            try:
                end, first, nsig = skip_tx(buf, start)
                print(f"  skip_tx@{start} OK nsig={nsig} end={end} first_is_N={first==SIG} span={end-start}")
            except Exception as e:
                print(f"  skip_tx@{start} FAIL {e}")

    # walk vec entries until fail
    nent = struct.unpack_from("<Q", buf, 0)[0]
    off = 8
    print("nent", nent)
    for e in range(nent):
        eoff = off
        try:
            num_h = struct.unpack_from("<Q", buf, off)[0]
            off += 40
            ntx = struct.unpack_from("<Q", buf, off)[0]
            off += 8
            if ntx > 4096:
                print(f"entry {e} FAIL ntx={ntx} at {eoff}")
                break
            hits = 0
            for t in range(ntx):
                off, first, nsig = skip_tx(buf, off)
                if first == SIG:
                    hits += 1
                    print(f"  N is entry={e} tx={t} nsig={nsig}")
            print(f"entry {e} ok num_h={num_h} ntx={ntx} off={off} N_hits={hits}")
        except Exception as ex:
            print(f"entry {e} FAIL at {off} {ex}")
            print(f"  context {buf[off:off+16].hex()}")
            break
    else:
        print("all entries parsed leftover", len(buf) - off)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
