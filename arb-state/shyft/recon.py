"""Append-only recon.bin writer. Same framing as STATE-006. No secrets."""
from __future__ import annotations

import os
import struct
from pathlib import Path

RECON_MAGIC = 0x36305453
RECON_AUTH = 3
RECON_INVALIDATE = 4
RECON_PLANE = 5


def open_recon(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("wb") as f:
            f.write(struct.pack("<IHH", RECON_MAGIC, 1, 0))
            f.flush()
            os.fsync(f.fileno())
    return path.open("ab")


def write_rec(f, kind: int, proto: int, pool_idx: int, sig: bytes, slot: int, body: bytes = b"") -> None:
    if len(sig) != 64:
        sig = (sig + bytes(64))[:64]
    fixed = struct.pack("<BBHI", kind, proto, 0, pool_idx) + sig + struct.pack("<Q", slot)
    if len(fixed) != 80:
        raise RuntimeError("recon fixed")
    f.write(struct.pack("<I", 80 + len(body)))
    f.write(fixed)
    f.write(body)
    f.flush()


def invalidate(f, proto: int, pool_idx: int, rx_ns: int, slot: int) -> None:
    sig = struct.pack("<QQ", rx_ns, 0) + bytes(48)
    write_rec(f, RECON_INVALIDATE, proto, pool_idx, sig, slot)


def plane(f, ready: bool, slot: int) -> None:
    write_rec(f, RECON_PLANE, 0, 0, bytes(64), 1 if ready else 0)


def auth(f, proto: int, pool_idx: int, slot: int, body: bytes) -> None:
    write_rec(f, RECON_AUTH, proto, pool_idx, bytes(64), slot, body)
