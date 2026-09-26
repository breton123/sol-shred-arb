"""Read-only STATE-009 ring. Never writes. Never recreates the file."""
from __future__ import annotations

import mmap
import os
import struct
from typing import Optional

from dlmm_quote import Bin, Dlmm, Pump

MAGIC = 0x39304841
VER = 1
RING = 16
BLOB = 2048
HDR = 256
ENT = 2176
POOL_HDR = 64
POOL = POOL_HDR + RING * ENT
POOL_CAP = 4096
PATH = "/dev/shm/arb_auth009"
COHERENT = 1
INCOMPLETE = 2
GAPPED = 4
_ENT = struct.Struct("<QQIIQ64sBBH28x")
PROTO_DLMM = 1
PROTO_PUMP = 2


def open_ro(path: str = PATH) -> mmap.mmap:
    fd = os.open(path, os.O_RDONLY)
    try:
        return mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
    finally:
        os.close(fd)


def n_pools(mm: mmap.mmap) -> int:
    magic, ver, ring, n = struct.unpack_from("<IHHI", mm, 0)
    if magic != MAGIC or ver != VER or ring != RING:
        raise RuntimeError("authpub header mismatch")
    return n


def latest(mm: mmap.mmap, idx: int) -> Optional[dict]:
    if idx < 0 or idx >= POOL_CAP:
        return None
    off = HDR + idx * POOL
    seq = struct.unpack_from("<Q", mm, off)[0]
    if seq & 1:
        return None
    head = struct.unpack_from("<I", mm, off + 8)[0]
    if head == 0:
        return None
    eoff = off + POOL_HDR + ((head - 1) % RING) * ENT
    gen, slot, txn, flags, ver, sig, proto, coh, nblob = _ENT.unpack_from(mm, eoff)
    if not coh or not (flags & COHERENT) or (flags & (INCOMPLETE | GAPPED)):
        return None
    blob = bytes(mm[eoff + 128:eoff + 128 + min(nblob, BLOB)])
    return {
        "idx": idx,
        "generation": gen,
        "slot": slot,
        "txn_index": txn,
        "flags": flags,
        "proto": proto,
        "sig": bytes(sig),
        "blob": blob,
    }


def parse_dlmm(blob: bytes) -> Optional[Dlmm]:
    if len(blob) < 67:
        return None
    o = 0
    active, = struct.unpack_from("<i", blob, o); o += 4
    bin_step, = struct.unpack_from("<H", blob, o); o += 2
    status = blob[o]; o += 1
    bf, fp, dp, rf = struct.unpack_from("<HHHH", blob, o); o += 8
    vfc, mva = struct.unpack_from("<II", blob, o); o += 8
    pshare, = struct.unpack_from("<H", blob, o); o += 2
    power = blob[o]; o += 1
    fee_mode = blob[o]; o += 1
    vacc, vref = struct.unpack_from("<II", blob, o); o += 8
    iref, = struct.unpack_from("<i", blob, o); o += 4
    last, = struct.unpack_from("<q", blob, o); o += 8
    rx, ry = struct.unpack_from("<QQ", blob, o); o += 16
    now, = struct.unpack_from("<q", blob, o); o += 8
    nbin, = struct.unpack_from("<H", blob, o); o += 2
    bins = []
    for _ in range(nbin):
        if o + 20 > len(blob):
            return None
        bid, x, y = struct.unpack_from("<iQQ", blob, o)
        o += 20
        bins.append(Bin(bid, x, y))
    return Dlmm(
        active, bin_step, status, bf, fp, dp, rf, vfc, mva, pshare, power,
        fee_mode, vacc, vref, iref, last, rx, ry, now, bins,
    )


def parse_pump(blob: bytes) -> Optional[Pump]:
    if len(blob) < 50:
        return None
    rb, rq, vq, lp, proto, creator = struct.unpack_from("<QQqQQQ", blob, 0)
    disabled = blob[48]
    status = blob[49]
    return Pump(rb, rq, vq, lp, proto, creator, disabled, status)
