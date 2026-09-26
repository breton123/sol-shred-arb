#!/usr/bin/env python3
"""Control-plane RPC for the 64-slot nonce ring and fee numbers.

Writes ctrl.bin (CTL1). The C plane only nonce_load / nonce_reload.
Does not create 64 nonce accounts. Does not enter the opportunity path.
Never prints secrets.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "arb-cap" / "exec_ctrl"
MAGIC = 0x314C5443
VER = 1
N = 64
NONCE_HASH_OFF = 40
NONCE_STATE_OFF = 4


def parse_nonce(data: bytes) -> bytes | None:
    if len(data) < 72:
        return None
    state = struct.unpack_from("<I", data, NONCE_STATE_OFF)[0]
    if state != 1:
        return None
    return data[NONCE_HASH_OFF : NONCE_HASH_OFF + 32]


def write_bin(path: Path, recs: list[tuple[bytes, bytes]], cu_price: int, min_profit: int) -> None:
    if len(recs) != N:
        raise SystemExit(f"need {N} records, got {len(recs)}")
    buf = bytearray(24 + N * 64)
    struct.pack_into("<IHHQQ", buf, 0, MAGIC, VER, N, cu_price, min_profit)
    for i, (pk, h) in enumerate(recs):
        off = 24 + i * 64
        buf[off : off + 32] = pk
        buf[off + 32 : off + 64] = h
    path.write_bytes(buf)


def main() -> int:
    live.load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--pubkeys", help="file of 64 base58 nonce account pubkeys")
    ap.add_argument("--cu-price", type=int, default=1000)
    ap.add_argument("--min-profit", type=int, default=1)
    ap.add_argument("--out", default=str(OUT / "ctrl.bin"))
    args = ap.parse_args()

    recs: list[tuple[bytes, bytes]] = []
    meta: list[dict] = []
    if args.pubkeys:
        lines = [
            ln.strip()
            for ln in Path(args.pubkeys).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")
        ]
        if len(lines) != N:
            raise SystemExit(f"{args.pubkeys}: want {N} pubkeys, got {len(lines)}")
        accs = d.get_multiple(lines)
        for pk, a in zip(lines, accs):
            if a is None:
                raise SystemExit(f"missing nonce account {pk[:8]}..")
            h = parse_nonce(a["data"])
            if h is None:
                raise SystemExit(f"not an initialized nonce {pk[:8]}..")
            recs.append((d.b58decode(pk), h))
            meta.append({"pubkey": pk, "hash": h.hex()})
        print(f"fetched {N} nonce hashes (rpc url redacted)")
    else:
        for i in range(N):
            pk = bytes([0xB0, i & 0xFF, (i >> 8) & 0xFF]) + bytes(29)
            h = bytes([0xC0, i & 0xFF, (i >> 8) & 0xFF]) + bytes(29)
            recs.append((pk, h))
            meta.append({"i": i, "synthetic": True})
        print(f"synthetic {N} (no --pubkeys; no RPC)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_bin(out, recs, args.cu_price, args.min_profit)
    (out.with_suffix(".json")).write_text(
        json.dumps(
            {
                "n": N,
                "cu_price": args.cu_price,
                "min_profit": args.min_profit,
                "path": str(out),
                "rpc": bool(args.pubkeys),
                "slots": meta,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out}  cu_price={args.cu_price}  min_profit={args.min_profit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
