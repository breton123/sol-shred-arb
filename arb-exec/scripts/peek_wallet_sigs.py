#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/louis/arb-cap")
import live001 as live
import record_dlmm as d

W = "HHNzjTABPAbPY5uEXU7NTvfmcD9RYTdXtLntyKAtpXLX"


def main():
    live.load_dotenv()
    print("sol", d.rpc("getBalance", [W]) / 1e9)
    sigs = d.rpc("getSignaturesForAddress", [W, {"limit": 8}]) or []
    for s in sigs:
        print(s.get("blockTime"), s.get("err"), (s.get("signature") or "")[:44],
              (s.get("memo") or "")[:40])


if __name__ == "__main__":
    raise SystemExit(main() or 0)
