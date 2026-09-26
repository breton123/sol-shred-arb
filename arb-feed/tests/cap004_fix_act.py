#!/usr/bin/env python3
"""Recompute actionable_off from cached trigger tx bytes. No RPC."""
from __future__ import annotations

import json
from pathlib import Path

PAIRS = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004\pairs.jsonl")

def cu16(p, off):
    b0 = p[off]
    if b0 < 0x80:
        return b0, off + 1
    b1 = p[off + 1]
    if b1 < 0x80:
        return (b0 & 0x7F) | (b1 << 7), off + 2
    b2 = p[off + 2]
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


# known infra (32-byte)
def b58(s):
    A = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in s:
        n = n * 58 + A.index(c)
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    h = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * pad + h
    return raw[-32:] if len(raw) >= 32 else raw.rjust(32, b"\x00")


INFRA = {
    b58("11111111111111111111111111111111"),
    b58("ComputeBudget111111111111111111111111111111"),
    b58("Vote111111111111111111111111111111111111111"),
    b58("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"),
    b58("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"),
    b58("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"),
    b58("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"),
    b58("AddressLookupTab1e1111111111111111111111111"),
    b58("Sysvar1nstructions1111111111111111111111111"),
    b58("Ed25519SigVerify111111111111111111111111111"),
}

DLMM = bytes([0x04,0xE9,0xE1,0x2F,0xBC,0x84,0xE8,0x26,0xC9,0x32,0xCC,0xE9,0xE2,0x64,0x0C,0xCE,0x15,0x59,0x0C,0x1C,0x62,0x73,0xB0,0x92,0x57,0x08,0xBA,0x3B,0x85,0x20,0xB0,0xBC])
PUMP = bytes([0x0C,0x14,0xDE,0xFC,0x82,0x5E,0xC6,0x76,0x94,0x25,0x08,0x18,0xBB,0x65,0x40,0x65,0xF4,0x29,0x8D,0x31,0x56,0xD5,0x71,0xB4,0xD4,0xF8,0x09,0x0C,0x18,0xE9,0xA8,0x63])


def actionable(raw: bytes):
    if not raw or len(raw) < 80:
        return None, None
    nsig, off = cu16(raw, 0)
    if nsig == 0 or nsig > 64:
        return len(raw), "unknown"
    off += nsig * 64
    if raw[off] & 0x80:
        off += 2
    else:
        off += 1
    off += 2
    nkeys, off = cu16(raw, off)
    keys = off
    off += nkeys * 32 + 32
    ninstr, off = cu16(raw, off)
    best = None
    proto = None
    for _ in range(ninstr):
        pi = raw[off]
        off += 1
        nacc, off = cu16(raw, off)
        accs = raw[off : off + nacc]
        off += nacc
        dlen, off = cu16(raw, off)
        data_off = off
        off += dlen
        if pi >= nkeys:
            continue
        pid = raw[keys + pi * 32 : keys + pi * 32 + 32]
        if pid in INFRA:
            continue
        need = [keys + pi * 32 + 32]
        if accs and accs[0] < nkeys:
            need.append(keys + accs[0] * 32 + 32)
        need.append(data_off + min(dlen, 16))
        end = max(need)
        if pid == DLMM:
            proto, best = "dlmm", end
            break
        if pid == PUMP:
            proto, best = "pump", end
            break
        if best is None:
            proto, best = "other", end
    if best is None:
        return len(raw), "unknown"
    return best, proto


def main():
    rows = [json.loads(l) for l in PAIRS.read_text(encoding="utf-8").splitlines() if l.strip()]
    n = 0
    proto = {}
    for r in rows:
        hx = r.get("trigger_tx_hex") or ""
        if not hx:
            continue
        raw = bytes.fromhex(hx)
        off, p = actionable(raw)
        r["actionable_off"] = off
        r["actionable_proto"] = p
        r["actionable_ok"] = off is not None
        proto[p] = proto.get(p, 0) + 1
        n += 1
    with PAIRS.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print("updated", n, "proto", proto)


if __name__ == "__main__":
    main()
