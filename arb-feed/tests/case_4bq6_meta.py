#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ARB = Path(r"C:\Users\louis\Desktop\ArbResearch")
sys.path.insert(0, str(ARB))
from dataset.env import helius_rpc_url  # noqa: E402

OUT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\case_4bq6")
PIDS = [
    "6e1x3suTHvzC3DPZR3jCXjDvKFjc9A2SGk99TbjkLPDP",
    "5N8FoU1cQ6SZ3cts6RNbGQvDCaSzTJjjyiG9s5V1uDNG",
    "B5MvUwXdiW1NMM6QFFD3ssPKBujD4zMohncbM73Z2BQu",
]


def rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(helius_rpc_url(), data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def main():
    meta = []
    for pid in PIDS:
        body = rpc("getAccountInfo", [pid, {"encoding": "jsonParsed"}])
        val = (body.get("result") or {}).get("value") or {}
        data = val.get("data")
        info = {}
        if isinstance(data, dict):
            info = (data.get("parsed") or {}).get("info") or {}
        meta.append(
            {
                "account": pid,
                "owner": val.get("owner"),
                "lamports": val.get("lamports"),
                "authority": info.get("authority"),
                "slot": info.get("slot"),
            }
        )
        time.sleep(0.15)
        print(pid[:8], info.get("authority"), info.get("slot"), flush=True)

    das = {}
    dp = OUT / "das_assets.json"
    if dp.exists():
        raw = json.loads(dp.read_text(encoding="utf-8"))
        res = (raw.get("result") or raw) if isinstance(raw, dict) else {}
        native = ((res.get("nativeBalance") or {}) if isinstance(res, dict) else {})
        items = []
        for a in res.get("items") or []:
            id_ = a.get("id")
            token = a.get("token_info") or {}
            items.append(
                {
                    "id": id_,
                    "symbol": (a.get("content") or {}).get("metadata", {}).get("symbol") or token.get("symbol"),
                    "balance": token.get("balance"),
                    "decimals": token.get("decimals"),
                    "price": (token.get("price_info") or {}).get("price_per_token"),
                    "value": (token.get("price_info") or {}).get("total_price"),
                }
            )
        das = {
            "native_lamports": native.get("lamports"),
            "native_sol": (native.get("lamports") or 0) / 1e9,
            "items": items[:30],
            "n_items": len(res.get("items") or []),
        }

    samples = json.loads((OUT / "samples.json").read_text(encoding="utf-8"))
    parsed = []
    for s in samples:
        parsed.append({"tag": s.get("tag"), "parsed": s.get("parsed"), "top": s.get("top"), "err": s.get("err")})

    out = {"program_data": meta, "das": das}
    (OUT / "meta.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:4000])


if __name__ == "__main__":
    main()
