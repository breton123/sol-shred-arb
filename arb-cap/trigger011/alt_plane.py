#!/usr/bin/env python3
"""Live ALT control plane. Off-path only.

Tails ~/captures/trigger011/alt_miss.jsonl, fetches lookup tables,
writes alt_cache.bin for paper_orbit to reload. Never called from the
shred loop.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

sys_path = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(sys_path))
from b58 import b58decode, b58encode
from alt_rpc import fetch_record, merge_record, write_cache
from rpc_url import rpc_url

DIR = Path(os.environ.get("TRIGGER011_DIR", str(Path.home() / "captures" / "trigger011")))
MISS = DIR / "alt_miss.jsonl"
JSON_OUT = DIR / "alt_cache.json"
BIN_OUT = DIR / "alt_cache.bin"
MET = DIR / "alt_plane.json"


def rpc(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def fetch_one(url: str, pk: str) -> dict | None:
    return fetch_record(rpc, url, pk, b58encode)


def refresh_due(cache: dict, due: dict, attempts: dict, url: str, now: float,
                fetcher=fetch_one) -> tuple[bool, int, int]:
    changed, success, failed = False, 0, 0
    for pk in sorted(due, key=due.get)[:8]:
        if due[pk] > now:
            break
        try:
            record = fetcher(url, pk)
        except Exception:
            attempts[pk] = attempts.get(pk, 0) + 1
            due[pk] = now + min(60, 2 ** min(attempts[pk], 6))
            failed += 1
            continue
        attempts.pop(pk, None)
        due[pk] = now + 30
        if record is None:
            if not (isinstance(cache.get(pk), dict) and cache[pk].get("quarantined")):
                changed |= cache.pop(pk, None) is not None
        else:
            cache[pk] = merge_record(cache.get(pk), record)
            changed = True
        success += 1
    return changed, success, failed


def main() -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    url = rpc_url()
    cache = {}
    if JSON_OUT.exists():
        cache = json.loads(JSON_OUT.read_text(encoding="utf-8"))
    due = dict.fromkeys(cache, 0.0)  # Old list-only caches are refetched.
    attempts = {}
    pos = 0
    fetches = 0
    hits = 0
    fails = 0
    print(f"ALT-PLANE  dir={DIR} cached={len(cache)} FUNDED=0", flush=True)
    while True:
        if MISS.exists():
            if MISS.stat().st_size < pos:
                pos = 0
            with MISS.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                for _ in range(1000):
                    line = f.readline()
                    if not line.endswith("\n"):
                        break  # Retry incomplete records on the next poll.
                    pos = f.tell()
                    try:
                        hx = json.loads(line).get("alt_hex", "")
                        if len(hx) == 64:
                            due.setdefault(b58encode(bytes.fromhex(hx)), 0.0)
                    except (ValueError, TypeError, AttributeError):
                        continue
        changed, ok, bad = refresh_due(cache, due, attempts, url, time.monotonic())
        fetches += ok + bad
        hits += ok
        fails += bad
        if changed:
            write_cache(cache, JSON_OUT, BIN_OUT, b58decode)
        if ok or bad:
            MET.write_text(json.dumps({
                "cache": len(cache),
                "fetches": fetches,
                "hits": hits,
                "fails": fails,
                "unique_miss": len(due),
                "retrying": len(attempts),
                "quarantined": sum(isinstance(r, dict) and r.get("quarantined", False) for r in cache.values()),
            }), encoding="utf-8")
            print(f"ALT-PLANE  cache={len(cache)} fetch={fetches} fail={fails}", flush=True)
        time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(main())
