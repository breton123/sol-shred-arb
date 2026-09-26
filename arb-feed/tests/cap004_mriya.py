#!/usr/bin/env python3
"""Pull Mriya rows from MEV.live for the trial wall-clock window. Does not touch ArbResearch state."""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

MRIYA = "MriyaNN8TMp6qRWjfr723PK7xgQK7yCt7Kg2v2PQu7X"
BASE = "https://mev.live/api/arb-explorer/search"
HEADERS = {
    "Referer": "https://mev.live/arbitrages",
    "Origin": "https://mev.live",
    "User-Agent": "arb-off/cap004",
}


def search(**params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(f"{BASE}?{q}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def walk(t0: int, t1: int, min_width: int = 1, user: str | None = MRIYA):
    resp = search(
        user=user,
        sort_by="time",
        sort_dir="desc",
        time_from=t0,
        time_to=t1,
        recent_mint_window_secs=0,
    )
    rows = resp.get("rows") or []
    total = int(resp.get("total_count") or 0)
    if total == 0:
        return
    if len(rows) >= total or (t1 - t0) <= min_width:
        for r in rows:
            yield r
        return
    mid = (t0 + t1) // 2
    if mid <= t0 or mid >= t1:
        for r in rows:
            yield r
        return
    time.sleep(0.05)
    yield from walk(t0, mid, min_width, user)
    yield from walk(mid, t1, min_width, user)


def main():
    t0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1790205095
    t1 = int(sys.argv[2]) if len(sys.argv) > 2 else 1790217009
    out = sys.argv[3] if len(sys.argv) > 3 else "mriya_trial.jsonl"
    want_all = len(sys.argv) > 4 and sys.argv[4] == "all"
    user = None if want_all else MRIYA
    n = 0
    seen = set()
    with open(out, "w", encoding="utf-8") as f:
        for row in walk(t0, t1, user=user):
            sig = row.get("signature")
            if not sig or sig in seen:
                continue
            if user and row.get("user") and row["user"] != user:
                continue
            seen.add(sig)
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
            n += 1
    print(f"wrote {n} rows user={user} {t0}..{t1} -> {out}")


if __name__ == "__main__":
    main()
