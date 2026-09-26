#!/usr/bin/env python3
"""Read-only: why slot 450394585 batch parse failed for N #4."""
from __future__ import annotations

import struct
import sys
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
        raise ValueError("nsig %d" % nsig)
    first = p[off:off + 64]
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
        raise ValueError("legacy")
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
    return off, first


def parse_vec(buf):
    nent = struct.unpack_from("<Q", buf, 0)[0]
    if nent == 0 or nent > 4096:
        raise ValueError("nent %d" % nent)
    off = 8
    sigs = []
    for _ in range(nent):
        off += 40
        ntx = struct.unpack_from("<Q", buf, off)[0]
        off += 8
        if ntx > 4096:
            raise ValueError("ntx %d" % ntx)
        for _t in range(ntx):
            off, first = skip_tx(buf, off)
            sigs.append(first)
    return nent, sigs, off, len(buf) - off


def try_parse(label, buf):
    print(f"  {label} len={len(buf)} head={buf[:32].hex()}")
    if len(buf) >= 8:
        print(f"    u64[0]={struct.unpack_from('<Q', buf, 0)[0]}")
    try:
        nent, sigs, used, pad = parse_vec(buf)
        hit = any(s == SIG for s in sigs)
        print(f"    VEC_OK nent={nent} ntx={len(sigs)} used={used} pad={pad} N_in_txs={hit}")
        return True
    except Exception as e:
        print(f"    VEC_FAIL {type(e).__name__}: {e}")
    return False


def main():
    recs = []
    with CAP.open("rb") as f:
        if f.read(8) != b"FEEDCAP1":
            print("bad magic")
            return 1
        f.seek(40)
        while True:
            rec = f.read(24)
            if len(rec) < 24:
                break
            _rx, _tsc, ln, _seq = struct.unpack("<QQII", rec)
            p = f.read(ln)
            if len(p) < 88 or (p[64] & 0xF0) not in DATA:
                continue
            slot = struct.unpack_from("<Q", p, 65)[0]
            if slot != SLOT:
                continue
            index = struct.unpack_from("<I", p, 73)[0]
            fec = struct.unpack_from("<I", p, 79)[0]
            flags = p[85]
            size = struct.unpack_from("<H", p, 86)[0]
            pos = p.find(SIG)
            recs.append((index, fec, flags, size, ln, p, pos))
    recs.sort(key=lambda x: x[0])
    print(f"slot {SLOT} nshred={len(recs)} unique_idx={len({r[0] for r in recs})}")
    print(f"idx_min={recs[0][0] if recs else None} idx_max={recs[-1][0] if recs else None}")
    completes = [r for r in recs if r[2] & 0x80]
    print(f"DATA_COMPLETE n={len(completes)} idxs={[r[0] for r in completes[:12]]}")
    hits = [r for r in recs if r[6] >= 0]
    print(f"SIG hits n={len(hits)}")
    for r in hits[:4]:
        print(f"  idx={r[0]} fec={r[1]} fl=0x{r[2]:02x} size={r[3]} ln={r[4]} pos={r[6]}")
    if not recs:
        return 1
    from collections import Counter
    print("size-ln", Counter((r[3], r[4]) for r in recs[:200]))
    print("fec", Counter(r[1] for r in recs))

    def concat(rows, strip_tail=0):
        buf = bytearray()
        for _idx, _fec, _fl, sz, ln, p, _pos in rows:
            if 88 <= sz <= ln:
                chunk = p[88:sz]
                if strip_tail and len(chunk) > strip_tail:
                    chunk = chunk[:-strip_tail]
                buf += chunk
        return bytes(buf)

    # unique by index, last write
    by_i = {}
    for r in recs:
        by_i[r[0]] = r
    ordered = [by_i[i] for i in sorted(by_i)]
    print("contiguous", all(ordered[i][0] == ordered[0][0] + i for i in range(len(ordered))))
    try_parse("all_size", concat(ordered, 0))
    try_parse("all_size_strip32", concat(ordered, 32))
    fec160 = [r for r in ordered if r[1] == 160]
    try_parse("fec160", concat(fec160, 0))
    try_parse("fec160_strip32", concat(fec160, 32))
    # from previous complete+1 to first complete after 187
    after = [r for r in completes if r[0] >= 187]
    if after:
        end = after[0][0]
        prev = [r[0] for r in completes if r[0] < 187]
        start = (prev[-1] + 1) if prev else ordered[0][0]
        run = [r for r in ordered if start <= r[0] <= end]
        print(f"run {start}..{end} n={len(run)}")
        try_parse("run_size", concat(run, 0))
        try_parse("run_strip32", concat(run, 32))
        try_parse("run_fullpkt_after88", b"".join(r[5][88:] for r in run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
