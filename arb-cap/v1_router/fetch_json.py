#!/usr/bin/env python3
"""Off-path getTransaction JSON for the 590 v1 winners. Labels only. No hot path."""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "arb-cap" / "frame_v1" / "winners.jsonl"
OUT = Path(__file__).resolve().parent / "txjson"


def rpc_url() -> str:
    for p in (ROOT / ".env", Path.home() / ".arb-state007.env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("SHYFT_KEY="):
                return "https://rpc.shyft.to?api_key=" + line.split("=", 1)[1].strip()
            if line.startswith("HELIUS_RPC_URL=") or line.startswith("RPC_URL="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("no rpc")


def rpc(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    last = None
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode())
            if data.get("error"):
                last = data["error"]
                time.sleep(0.2 * (i + 1))
                continue
            return data.get("result")
        except Exception as e:
            last = e
            time.sleep(0.2 * (i + 1))
    return {"_error": str(last)[:180]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    url = rpc_url()
    sigs = []
    for line in META.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") == "v1":
            sigs.append(r["sig"])
    todo = [s for s in sigs if not (OUT / (s + ".json")).exists()]
    print("v1", len(sigs), "todo", len(todo), flush=True)

    def work(sig):
        dest = OUT / (sig + ".json")
        doc = rpc(url, "getTransaction", [sig, {
            "encoding": "json",
            "maxSupportedTransactionVersion": 1,
            "commitment": "confirmed",
        }])
        dest.write_text(json.dumps(doc), encoding="utf-8")
        return sig

    n = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for _ in as_completed([ex.submit(work, s) for s in todo]):
            n += 1
            if n % 50 == 0:
                print("json", n, "/", len(todo), flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
