"""STATE-009 AUTH-PUBLISH writer. Layout matches arb-feed/include/authpub.h."""
from __future__ import annotations

import mmap
import os
import struct
from pathlib import Path

MAGIC = 0x39304841
VER = 1
RING = 16
BLOB = 2048
HDR = 256
ENT = 2176
POOL_HDR = 64
POOL = POOL_HDR + RING * ENT
POOL_CAP = 4096

COHERENT = 1
INCOMPLETE = 2
GAPPED = 4
BOOT = 8
HAS_ACCOUNT_WRITE_VERSION = 16
HAS_TXN_INDEX = 32
TXN_INDEX_UNKNOWN = 0xFFFFFFFF

PATH_DEFAULT = "/dev/shm/arb_auth009"

# entry: gen u64, slot u64, txn_index u32, flags u32, state_ver u64,
# sig[64], proto u8, coherent u8, blob_len u16, max_write_version u64,
# reserved[12], blob[2048]. Header remains 128 bytes for C compatibility.
_ENT_HDR = struct.Struct("<QQIIQ64sBBHQ20x")


def map_size(pool_cap: int = POOL_CAP) -> int:
    return HDR + pool_cap * POOL


def fnv1a64(data: bytes) -> int:
    h = 14695981039346656037
    for b in data:
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def choose_pred(entries: list[dict], trig_slot: int, sig: bytes | None) -> dict | None:
    """Choose a proven predecessor from a newest-first ring; never skip a gap."""
    def usable(e: dict) -> bool:
        flags = int(e.get("flags", 0))
        return bool(e.get("coherent") and flags & COHERENT
                    and not flags & (INCOMPLETE | GAPPED))

    if sig:
        for i, e in enumerate(entries):
            if e.get("sig") == sig:
                if i + 1 < len(entries) and usable(entries[i + 1]):
                    return entries[i + 1]
                return None
    for e in entries:
        slot = int(e["slot"])
        if slot == int(trig_slot):
            return None  # Without the target signature, same-slot order is unknown.
        if slot < int(trig_slot):
            return e if usable(e) else None
    return None


class AuthPub:
    def __init__(self, path: str | Path | None = None, pool_cap: int = POOL_CAP) -> None:
        self.path = Path(path or PATH_DEFAULT)
        self.pool_cap = pool_cap
        self.mm: mmap.mmap | None = None
        self._ver: int = 0

    def create(self) -> None:
        size = map_size(self.pool_cap)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            os.ftruncate(fd, size)
            self.mm = mmap.mmap(fd, size)
        finally:
            os.close(fd)
        self.mm[0:HDR] = b"\x00" * HDR
        struct.pack_into("<IHHIIIIQQQ", self.mm, 0,
                         MAGIC, VER, RING, 0, self.pool_cap, BLOB, 0, 0, 0, 0)
        self._ver = 0
        for i in range(self.pool_cap):
            off = HDR + i * POOL
            self.mm[off:off + POOL] = b"\x00" * POOL

    def open(self) -> None:
        if not self.path.exists():
            self.create()
            return
        fd = os.open(str(self.path), os.O_RDWR)
        try:
            size = os.fstat(fd).st_size
            want = map_size(self.pool_cap)
            if size != want:
                os.close(fd)
                self.create()
                return
            self.mm = mmap.mmap(fd, size)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
        magic, ver, ring = struct.unpack_from("<IHH", self.mm, 0)
        if magic != MAGIC or ver != VER or ring != RING:
            self.create()
        else:
            self._ver = struct.unpack_from("<Q", self.mm, 24)[0]

    def close(self) -> None:
        if self.mm is not None:
            self.mm.flush()
            self.mm.close()
            self.mm = None

    def set_ready(self, ready: bool, n_pools: int = 0, slot: int = 0) -> None:
        if self.mm is None:
            return
        struct.pack_into("<I", self.mm, 8, int(n_pools))
        struct.pack_into("<I", self.mm, 20, 1 if ready else 0)
        struct.pack_into("<Q", self.mm, 40, int(slot))

    def reset_history(self) -> None:
        """Revoke readiness and hide prior-provider rings under their seqlocks."""
        if self.mm is None:
            return
        self.set_ready(False)
        self._ver += 1
        for idx in range(self.pool_cap):
            off = HDR + idx * POOL
            seq = struct.unpack_from("<Q", self.mm, off)[0]
            seq += seq & 1  # Recover an abandoned odd writer sequence.
            struct.pack_into("<Q", self.mm, off, seq + 1)
            struct.pack_into("<IIQ", self.mm, off + 8, 0, GAPPED, self._ver)
            struct.pack_into("<Q", self.mm, off, seq + 2)
        struct.pack_into("<Q", self.mm, 24, self._ver)

    def publish(
        self,
        idx: int,
        *,
        slot: int,
        blob: bytes,
        proto: int,
        sig: bytes | None,
        txn_index: int | None = None,
        max_account_write_version: int | None = None,
        flags: int = COHERENT,
        boot: bool = False,
    ) -> None:
        if self.mm is None or idx < 0 or idx >= self.pool_cap:
            return
        if len(blob) > BLOB:
            return
        raw = bytes(sig or b"")[:64]
        if boot or raw == b"boot":
            raw = b"\x00" * 64
            flags |= BOOT
        if len(raw) < 64:
            raw = raw + bytes(64 - len(raw))
        flags |= COHERENT
        if txn_index is None:
            txn = TXN_INDEX_UNKNOWN
        else:
            txn = int(txn_index)
            if txn < 0 or txn >= TXN_INDEX_UNKNOWN:
                raise ValueError("txn_index must fit u32; use None when unknown")
            flags |= HAS_TXN_INDEX
        write_ver = 0 if max_account_write_version is None else int(max_account_write_version)
        if write_ver < 0 or write_ver > 0xFFFFFFFFFFFFFFFF:
            raise ValueError("max_account_write_version must fit u64")
        if max_account_write_version is not None:
            flags |= HAS_ACCOUNT_WRITE_VERSION
        off = HDR + idx * POOL
        seq = struct.unpack_from("<Q", self.mm, off)[0]
        struct.pack_into("<Q", self.mm, off, seq + 1)  # odd: writing
        head = struct.unpack_from("<I", self.mm, off + 8)[0]
        slot_i = head % RING
        self._ver += 1
        eoff = off + POOL_HDR + slot_i * ENT
        _ENT_HDR.pack_into(
            self.mm, eoff,
            self._ver, int(slot), txn, flags, self._ver, raw,
            proto & 0xFF, 1, len(blob), write_ver,
        )
        self.mm[eoff + 128:eoff + 128 + BLOB] = bytes(BLOB)
        if blob:
            self.mm[eoff + 128:eoff + 128 + len(blob)] = blob
        struct.pack_into("<I", self.mm, off + 8, head + 1)
        struct.pack_into("<I", self.mm, off + 12, flags)
        struct.pack_into("<Q", self.mm, off + 16, self._ver)
        struct.pack_into("<Q", self.mm, 24, self._ver)  # global state_version
        struct.pack_into("<Q", self.mm, off, seq + 2)  # even: published

    def dump_ring(self, idx: int) -> list[dict]:
        if self.mm is None or idx >= self.pool_cap:
            return []
        off = HDR + idx * POOL
        head = struct.unpack_from("<I", self.mm, off + 8)[0]
        n = min(head, RING)
        out = []
        for i in range(n):
            eoff = off + POOL_HDR + ((head - 1 - i) % RING) * ENT
            gen, slot, txn, flags, ver, sig, proto, coh, nblob, write_ver = _ENT_HDR.unpack_from(self.mm, eoff)
            out.append({
                "generation": gen, "slot": slot,
                "txn_index": txn if flags & HAS_TXN_INDEX else TXN_INDEX_UNKNOWN,
                "flags": flags, "state_version": ver, "sig": bytes(sig),
                "proto": proto, "coherent": coh, "blob_len": nblob,
                "max_account_write_version": write_ver if flags & HAS_ACCOUNT_WRITE_VERSION else None,
            })
        return out
