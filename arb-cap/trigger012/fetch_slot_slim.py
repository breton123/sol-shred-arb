#!/usr/bin/env python3
"""Off-path getBlock → compact slim with resolved program ids.

Inner CPI is visible because programIdIndex is resolved against
static keys + loadedAddresses. No hot-path RPC.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker")
sys.path.insert(0, str(ROOT / "arb-cap" / "trigger011"))
from rpc_url import rpc_url  # noqa: E402

SLIM = Path(__file__).resolve().parent / "slim"
VOTE = "Vote111111111111111111111111111111111111111"
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


def pk_of(k) -> str | None:
    if isinstance(k, str):
        return k
    if isinstance(k, dict):
        return k.get("pubkey")
    return None


def rpc(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def slim_tx(i: int, tx: dict) -> dict:
    meta = tx.get("meta") or {}
    tr = tx.get("transaction") or {}
    msg = tr.get("message") or {}
    sigs = tr.get("signatures") or []
    sig = sigs[0] if sigs else ""
    err = bool(meta.get("err"))
    keys = [pk_of(k) for k in (msg.get("accountKeys") or [])]
    loaded = meta.get("loadedAddresses") or {}
    wr = [pk_of(k) or k for k in (loaded.get("writable") or [])]
    ro = [pk_of(k) or k for k in (loaded.get("readonly") or [])]
    resolved = [k for k in keys + wr + ro if k]
    pids = []
    seen = set()

    def add_pid(idx):
        if isinstance(idx, int) and 0 <= idx < len(resolved):
            pid = resolved[idx]
            if pid and pid not in seen:
                seen.add(pid)
                pids.append(pid)

    for ix in msg.get("instructions") or []:
        add_pid(ix.get("programIdIndex"))
    for g in meta.get("innerInstructions") or []:
        for ix in g.get("instructions") or []:
            add_pid(ix.get("programIdIndex"))
            pid = ix.get("programId")
            if pid and pid not in seen:
                seen.add(pid)
                pids.append(pid)
    vote = VOTE in pids
    return {
        "i": i,
        "sig": sig,
        "err": err,
        "vote": vote,
        "pids": pids,
        "dex": (DLMM in pids) or (PUMP in pids),
    }


def slim_block(slot: int, block: dict) -> dict:
    txs = []
    for i, tx in enumerate(block.get("transactions") or []):
        txs.append(slim_tx(i, tx))
    return {"slot": slot, "n": len(txs), "txs": txs}


def fetch_slot(url: str, slot: int) -> tuple[int, bool, str]:
    dest = SLIM / f"{slot}.json.gz"
    if dest.exists() and dest.stat().st_size > 20:
        try:
            with gzip.open(dest, "rt", encoding="utf-8") as f:
                prev = json.load(f)
            if prev.get("txs") and not prev.get("error"):
                return slot, True, "cached"
        except Exception:
            pass
        dest.unlink(missing_ok=True)
    last = ""
    for attempt in range(4):
        try:
            doc = rpc(url, "getBlock", [slot, {
                "encoding": "json",
                "transactionDetails": "full",
                "rewards": False,
                "maxSupportedTransactionVersion": 1,
            }])
            if doc.get("error"):
                last = str(doc["error"])
                time.sleep(0.8 * (attempt + 1))
                continue
            val = doc.get("result")
            if not val:
                last = "null"
                time.sleep(0.5)
                continue
            slim = slim_block(slot, val)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".tmp.gz")
            with gzip.open(tmp, "wt", encoding="utf-8") as f:
                json.dump(slim, f)
            tmp.replace(dest)
            return slot, True, "ok"
        except Exception as e:
            last = str(e)
            wait = 8.0 if "429" in last else 0.8
            time.sleep(wait * (attempt + 1))
    return slot, False, last[:80]


def slots_from_sources() -> list[int]:
    want = set()
    hour = Path(__file__).resolve().parent / "hour_arbs.jsonl"
    if hour.exists():
        for line in hour.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("slot"):
                want.add(int(r["slot"]))
    mev = json.loads((ROOT / "arb-cap" / "regress" / "mev_hour.json").read_text(encoding="utf-8"))
    for s in mev.get("dlmm_pump_slots") or []:
        want.add(int(s))
    return sorted(want)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    url = rpc_url()
    slots = slots_from_sources()
    def good(path: Path) -> bool:
        if not path.exists() or path.stat().st_size < 40:
            return False
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                doc = json.load(f)
            return bool(doc.get("txs")) and not doc.get("error")
        except Exception:
            return False

    need = [s for s in slots if not good(SLIM / f"{s}.json.gz")]
    print(f"slots={len(slots)} need={len(need)}", flush=True)
    ok = len(slots) - len(need)
    fail = 0
    if need:
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(fetch_slot, url, s) for s in need]
            done = 0
            for fut in as_completed(futs):
                slot, good, why = fut.result()
                done += 1
                if good:
                    ok += 1
                else:
                    fail += 1
                if done % 25 == 0 or not good:
                    print(f"  {done}/{len(need)} ok={ok} fail={fail} last={slot}:{why}", flush=True)
    print(f"slim done ok={ok} fail={fail} dir={SLIM}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
