#!/usr/bin/env python3
"""Connectivity probe. Does not print secrets."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")


def load_key(name: str) -> str:
    for p in (ROOT / ".env", Path(r"C:\Users\louis\Desktop\ArbResearch\atomic_arbitrage\long_hop_analysis\.env")):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def rpc(url: str, method: str, params) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def main() -> None:
    shyft = load_key("SHYFT_KEY")
    helius = load_key("HELIUS_API_KEY")
    for name, url in (
        ("shyft", "https://rpc.shyft.to?api_key=" + shyft if shyft else ""),
        ("helius", "https://mainnet.helius-rpc.com/?api-key=" + helius if helius else ""),
    ):
        if not url:
            print(name, "missing")
            continue
        try:
            data = rpc(url, "getSlot", [])
            print(name, "ok" if "result" in data else "err", "slot" if "result" in data else str(data.get("error"))[:80])
        except Exception as e:
            print(name, "fail", type(e).__name__)


if __name__ == "__main__":
    main()
