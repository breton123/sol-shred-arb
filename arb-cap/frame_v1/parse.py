"""FRAME-V1 reference parser. Matches arb-core/src/frame.c fail-closed rules."""
from __future__ import annotations

TX_SIG_MAX, TX_KEY_MAX, TX_INSTR_MAX = 12, 64, 64
TX_V1_PREFIX = 0x81
TX_V1_MAX = 4096
TX_V1_CFG_KNOWN = 0x1F
TX_V1_HDR = 42

PROG_DLMM = bytes.fromhex("04e9e12fbc84e826c932cce9e2640cce15590c1c6273b0925708ba3b8520b0bc")
PROG_PUMP = bytes.fromhex("0c14defc825ec67694250818bb654065f4298d3156d571b4d4f8090c18e9a863")
DLMM_SWAP2 = bytes.fromhex("414b3f4ceb5b5b88")
DLMM_SWAP1 = bytes.fromhex("f8c69e91e17587c8")
PUMP_SELL = bytes.fromhex("33e685a4017f83ad")
PUMP_BUY_EQ = bytes.fromhex("c62e1552b4d9e870")
PUMP_BUY = bytes.fromhex("66063d1201daebea")
EXACT = {DLMM_SWAP2, DLMM_SWAP1, PUMP_SELL, PUMP_BUY_EQ}


def cu16(b: bytes, off: int):
    if off >= len(b):
        return None
    b0 = b[off]
    if (b0 & 0x80) == 0:
        return b0, off + 1
    if off + 1 >= len(b):
        return None
    b1 = b[off + 1]
    if (b1 & 0x80) == 0:
        if b1 == 0:
            return "bad"
        return (b0 & 0x7F) | (b1 << 7), off + 2
    if off + 2 >= len(b):
        return None
    b2 = b[off + 2]
    if (b2 & 0xFC) != 0 or b2 == 0:
        return "bad"
    return (b0 & 0x7F) | ((b1 & 0x7F) << 7) | (b2 << 14), off + 3


def header_ok(nsig, ro_s, ro_u, nkeys) -> bool:
    if nsig < 1 or nsig > TX_SIG_MAX:
        return False
    if ro_s >= nsig:
        return False
    if nkeys < nsig or nkeys > TX_KEY_MAX:
        return False
    if nsig + ro_u > nkeys:
        return False
    return True


def _need(why: str) -> dict:
    return {"klass": "incomplete", "why": why, "ver": None}


def _bad(why: str) -> dict:
    return {"klass": "invalid", "why": why, "ver": None}


def parse_legacy_v0(raw: bytes, start: int = 0) -> dict:
    """Pre-FRAME-V1 framer. 0x81 is rejected as a bad versioned prefix or nsig."""
    p = raw[start:]
    got = cu16(p, 0)
    if got is None:
        return _need("truncated_nsig")
    if got == "bad":
        return _bad("bad_nsig")
    nsig, off = got
    if nsig < 1 or nsig > TX_SIG_MAX:
        return _bad("nsig_range")
    if off + nsig * 64 > len(p):
        return _need("truncated_sigs")
    off += nsig * 64
    if off >= len(p):
        return _need("truncated_hdr")
    b0 = p[off]
    off += 1
    versioned = False
    if b0 & 0x80:
        if (b0 & 0x7F) != 0:
            return _bad("bad_version")
        versioned = True
        if off >= len(p) or p[off] != nsig:
            return _bad("hdr_nsig")
        off += 1
    elif b0 != nsig:
        return _bad("hdr_nsig")
    if off + 2 > len(p):
        return _need("truncated_hdr")
    ro_s, ro_u = p[off], p[off + 1]
    off += 2
    got = cu16(p, off)
    if got is None:
        return _need("truncated_nkeys")
    if got == "bad":
        return _bad("bad_nkeys")
    nkeys, off = got
    if not header_ok(nsig, ro_s, ro_u, nkeys):
        return _bad("header")
    if off + nkeys * 32 + 32 > len(p):
        return _need("truncated_keys")
    keys = [p[off + i * 32: off + (i + 1) * 32] for i in range(nkeys)]
    off += nkeys * 32 + 32
    got = cu16(p, off)
    if got is None:
        return _need("truncated_ix")
    if got == "bad":
        return _bad("bad_ix")
    ninstr, off = got
    if ninstr == 0 or ninstr > TX_INSTR_MAX:
        return _bad("ninstr")
    ixs = []
    for _ in range(ninstr):
        if off >= len(p):
            return _need("truncated_ix")
        prog = p[off]
        off += 1
        if not versioned and prog >= nkeys:
            return _bad("prog_idx")
        got = cu16(p, off)
        if got is None or got == "bad":
            return _need("ix_acc") if got is None else _bad("ix_acc")
        nacct, off = got
        if off + nacct > len(p):
            return _need("truncated_acc")
        acc = list(p[off:off + nacct])
        off += nacct
        got = cu16(p, off)
        if got is None or got == "bad":
            return _need("ix_data") if got is None else _bad("ix_data")
        dlen, off = got
        if off + dlen > len(p):
            return _need("truncated_data")
        data = p[off:off + dlen]
        off += dlen
        ixs.append({"prog": prog, "acc": acc, "data": data})
    if versioned:
        got = cu16(p, off)
        if got is None or got == "bad":
            return _need("lut") if got is None else _bad("lut")
        nlut, off = got
        if nlut > 32:
            return _bad("nlut")
        for _ in range(nlut):
            if off + 32 > len(p):
                return _need("truncated_alt")
            off += 32
            for _w in range(2):
                got = cu16(p, off)
                if got is None or got == "bad":
                    return _need("alt_idx") if got is None else _bad("alt_idx")
                nw, off = got
                if off + nw > len(p):
                    return _need("truncated_alt_idx")
                off += nw
    return {
        "klass": "framed",
        "why": "ok",
        "ver": "v0" if versioned else "legacy",
        "nsig": nsig,
        "nkeys": nkeys,
        "ninstr": ninstr,
        "keys": keys,
        "ixs": ixs,
        "tx_end": start + off,
        "luts": versioned,
    }


def parse_v1(raw: bytes, start: int = 0) -> dict:
    p = raw
    if start >= len(p):
        return _need("truncated_prefix")
    if p[start] != TX_V1_PREFIX:
        return _bad("not_v1")
    if start + TX_V1_HDR > len(p):
        return _need("truncated_hdr")
    nsig = p[start + 1]
    ro_s = p[start + 2]
    ro_u = p[start + 3]
    mask = int.from_bytes(p[start + 4:start + 8], "little")
    if mask & ~TX_V1_CFG_KNOWN:
        return _bad("unknown_mask")
    if (mask & 3) in (1, 2):
        return _bad("partial_priority_fee")
    ninstr = p[start + 40]
    naddr = p[start + 41]
    if ninstr == 0 or ninstr > TX_INSTR_MAX:
        return _bad("ninstr")
    if not header_ok(nsig, ro_s, ro_u, naddr):
        return _bad("header")
    off = start + TX_V1_HDR
    if off + naddr * 32 > len(p):
        return _need("truncated_keys")
    keys = [p[off + i * 32: off + (i + 1) * 32] for i in range(naddr)]
    if len(set(keys)) != naddr:
        return _bad("duplicate_address")
    off += naddr * 32
    cfg_n = bin(mask).count("1") * 4
    if off + cfg_n > len(p):
        return _need("truncated_cfg")
    off += cfg_n
    if off + ninstr * 4 > len(p):
        return _need("truncated_ixhdr")
    headers = []
    pay = 0
    for i in range(ninstr):
        prog = p[off + i * 4]
        nacct = p[off + i * 4 + 1]
        dlen = p[off + i * 4 + 2] | (p[off + i * 4 + 3] << 8)
        if prog >= naddr:
            return _bad("prog_idx")
        headers.append((prog, nacct, dlen))
        pay += nacct + dlen
    off += ninstr * 4
    proj = (off - start) + pay + nsig * 64
    if proj > TX_V1_MAX:
        return _bad("oversize")
    if off + pay > len(p):
        return _need("truncated_payload")
    ixs = []
    cursor = off
    for prog, nacct, dlen in headers:
        if cursor + nacct + dlen > len(p):
            return _need("truncated_payload")
        acc = list(p[cursor:cursor + nacct])
        if any(a >= naddr for a in acc):
            return _bad("acc_idx")
        data = p[cursor + nacct:cursor + nacct + dlen]
        ixs.append({"prog": prog, "acc": acc, "data": data})
        cursor += nacct + dlen
    off = cursor
    if off + nsig * 64 > len(p):
        return _need("truncated_sigs")
    off += nsig * 64
    return {
        "klass": "framed",
        "why": "ok",
        "ver": "v1",
        "nsig": nsig,
        "nkeys": naddr,
        "ninstr": ninstr,
        "keys": keys,
        "ixs": ixs,
        "tx_end": off,
        "luts": False,
        "mask": mask,
    }


def parse_any(raw: bytes, start: int = 0) -> dict:
    if start < len(raw) and raw[start] == TX_V1_PREFIX:
        return parse_v1(raw, start)
    return parse_legacy_v0(raw, start)


def wire_kind(raw: bytes) -> str:
    if not raw:
        return "empty"
    if raw[0] == TX_V1_PREFIX:
        return "v1"
    got = cu16(raw, 0)
    if got is None or got == "bad":
        return "unknown"
    nsig, off = got
    if nsig < 1 or off + nsig * 64 >= len(raw):
        return "unknown"
    b0 = raw[off + nsig * 64]
    if b0 == 0x80:
        return "v0"
    return "legacy"


def classify_ixs(parsed: dict) -> dict:
    keys = parsed.get("keys") or []
    n_exact = 0
    n_unknown = 0
    n_other = 0
    for ix in parsed.get("ixs") or []:
        prog = ix["prog"]
        if prog >= len(keys):
            n_unknown += 1
            continue
        pk = keys[prog]
        data = ix["data"]
        if pk in (PROG_DLMM, PROG_PUMP):
            if len(data) >= 24 and data[:8] in EXACT:
                n_exact += 1
            elif len(data) >= 8 and data[:8] == PUMP_BUY:
                n_unknown += 1
            else:
                n_unknown += 1
        else:
            n_other += 1
    if n_exact and n_unknown == 0:
        stage = "TX_EXACT"
    elif n_exact:
        stage = "IX_EXACT"
    else:
        stage = "UNKNOWN"
    return {
        "n_exact": n_exact,
        "n_unknown_dex": n_unknown,
        "n_other": n_other,
        "stage": stage,
        "dex_static": any(k in (PROG_DLMM, PROG_PUMP) for k in keys),
    }
