#!/usr/bin/env python3
"""Off-path ALT control plane. No hot-path RPC.

Collects Address Lookup Table pubkeys from:
  - late-121 trigger bytes
  - live alt_miss.jsonl
Fetches finalized getAccountInfo plus observation bank hash and writes:
  alt_cache.json
  alt_cache.bin  (ALT2, consumed by paper_orbit)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from b58 import b58decode, b58encode
from alt_rpc import fetch_record, merge_record, write_cache
from hist_funnel011 import attach_hex, load_races, parse_any
from rpc_url import rpc_url

OUT_DIR = Path(r"c:\Users\louis\Desktop\TheMoneyMaker") / "arb-cap" / "trigger011"
LIVE_MISS = Path("/home/louis/captures/trigger011/alt_miss.jsonl")
JSON_OUT = OUT_DIR / "alt_cache.json"
BIN_OUT = OUT_DIR / "alt_cache.bin"


def rpc(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def fetch_one(url: str, pk: str) -> dict | None:
    return fetch_record(rpc, url, pk, b58encode)


def collect_luts() -> set[str]:
    want: set[str] = set()
    rows = load_races()
    attach_hex(rows)
    for r in rows:
        hx = r.get("trigger_tx_hex") or ""
        if not hx:
            continue
        parsed = parse_any(bytes.fromhex(hx))
        for lut in parsed.get("luts") or []:
            want.add(lut)
    if LIVE_MISS.exists():
        for line in LIVE_MISS.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            hx = rec.get("alt_hex") or ""
            if len(hx) == 64:
                want.add(b58encode(bytes.fromhex(hx)))
    return want


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    url = rpc_url()
    existing = {}
    if JSON_OUT.exists():
        existing = json.loads(JSON_OUT.read_text(encoding="utf-8"))
    want = collect_luts() | set(existing)
    print(f"unique ALTs requested={len(want)} already={len(existing)}")
    ok = 0
    fail = 0
    t0 = time.time()
    for i, pk in enumerate(sorted(want)):
        try:
            record = fetch_one(url, pk)
        except Exception:
            fail += 1
            continue
        if record is not None:
            existing[pk] = merge_record(existing.get(pk), record)
            ok += 1
        else:
            existing.pop(pk, None)
            fail += 1
        if (i + 1) % 10 == 0:
            print(f"  progress {i+1}/{len(want)} ok={ok} fail={fail}")
        time.sleep(0.05)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_cache(existing, JSON_OUT, BIN_OUT, b58decode)
    print(f"wrote {JSON_OUT.name} n={len(existing)} ok={ok} fail={fail} "
          f"lat_s={time.time()-t0:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
