#!/usr/bin/env python3
"""Re-fetch predecessor txs that classify_pred cached as missing."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify_pred as cp  # noqa: E402

FUNNEL = HERE / "funnel012.jsonl"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = [json.loads(l) for l in FUNNEL.read_text(encoding="utf-8").splitlines() if l.strip()]
    need = []
    for r in rows:
        if r.get("stage") != "pred_tx_missing" or not r.get("pred_sig"):
            continue
        p = cp.cache_path(r["pred_sig"])
        if p.exists():
            p.unlink()
        need.append(r["pred_sig"])
    need = list(dict.fromkeys(need))
    print(f"retry {len(need)}", flush=True)
    url = cp.rpc_url()
    from concurrent.futures import ThreadPoolExecutor, as_completed
    ok = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(cp.fetch_one, url, s) for s in need]
        for i, fut in enumerate(as_completed(futs), 1):
            fut.result()
            if i % 50 == 0:
                print(f"  {i}/{len(need)}", flush=True)
    for s in need:
        tx = cp.load_tx(s)
        if tx and not tx.get("_error"):
            ok += 1
    print(f"recovered {ok}/{len(need)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
