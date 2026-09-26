#!/usr/bin/env python3
"""Fetch raw bytes for the 2464 historical DLMM/Pump winners. Off-path RPC."""
from __future__ import annotations

import base64
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "arb-cap" / "frame_v1"))
from parse import wire_kind  # noqa: E402

ARBS = ROOT / "arb-cap" / "trigger012" / "hour_arbs.jsonl"
OUT = Path(__file__).resolve().parent
RAW = OUT / "raw"
META = OUT / "winners.jsonl"


def rpc_url() -> str:
    for p in (
        ROOT / ".env",
        Path.home() / ".arb-state007.env",
        Path("/home/louis/TheMoneyMaker/.env"),
    ):
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
    for i in range(5):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode())
            if data.get("error"):
                last = data["error"]
                time.sleep(0.25 * (i + 1))
                continue
            return data.get("result")
        except Exception as e:
            last = e
            time.sleep(0.25 * (i + 1))
    return None


def load_arbs():
    rows = []
    for line in ARBS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fetch_one(url: str, sig: str) -> bytes | None:
    dest = RAW / (sig + ".bin")
    if dest.exists() and dest.stat().st_size > 0:
        return dest.read_bytes()
    doc = rpc(url, "getTransaction", [sig, {
        "encoding": "base64",
        "maxSupportedTransactionVersion": 1,
        "commitment": "confirmed",
    }])
    if not doc:
        return None
    tx = doc.get("transaction")
    raw = None
    if isinstance(tx, list) and tx:
        raw = base64.b64decode(tx[0])
    elif isinstance(tx, dict) and isinstance(tx.get("message"), str):
        raw = base64.b64decode(tx["message"])
    if not raw:
        return None
    dest.write_bytes(raw)
    return raw


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    url = rpc_url()
    arbs = load_arbs()
    print("winners", len(arbs), flush=True)
    done = {}
    if META.exists():
        for line in META.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["sig"]] = r
    todo = [a for a in arbs if a["sig"] not in done]
    print("cached", len(done), "todo", len(todo), flush=True)

    def work(a):
        raw = fetch_one(url, a["sig"])
        kind = wire_kind(raw) if raw else "missing"
        return {
            "sig": a["sig"],
            "slot": a.get("slot"),
            "usd": a.get("usd"),
            "kind": kind,
            "n": 0 if raw is None else len(raw),
        }

    workers = 8
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, a) for a in todo]
        n = 0
        with META.open("a", encoding="utf-8") as out:
            for fut in as_completed(futs):
                rec = fut.result()
                out.write(json.dumps(rec) + "\n")
                out.flush()
                n += 1
                if n % 50 == 0:
                    print("fetched", n, "/", len(todo), flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
