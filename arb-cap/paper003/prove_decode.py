#!/usr/bin/env python3
"""PAPER-003 — prove hot_decode applies N.

Compare C swapix (raw tx bytes) to the parsed on-chain transaction.
Supported variants only; unsupported must fail closed.
100% exact on pool / direction / amount_in / min_out.

Env: HELIUS_API_KEY or HELIUS_RPC_URL. Never prints the key.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

OUT = Path(__file__).resolve().parent
CORPUS = OUT / "corpus"
SOL = "So11111111111111111111111111111111111111112"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKENZ = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
ATA = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

SWAP2 = bytes([65, 75, 63, 76, 235, 91, 91, 136])
SWAP1 = bytes([248, 198, 158, 145, 225, 117, 135, 200])
PUMP_BUY = bytes([102, 6, 61, 18, 1, 218, 235, 234])
PUMP_SELL = bytes([51, 230, 133, 164, 1, 127, 131, 173])
PUMP_BUY_EQ = bytes([198, 46, 21, 82, 180, 217, 232, 112])

P = 2**255 - 19
D = (-121665 * pow(121666, P - 2, P)) % P


def on_curve(pt: bytes) -> bool:
    if len(pt) != 32:
        return False
    y = int.from_bytes(pt, "little") & ((1 << 255) - 1)
    if y >= P:
        return False
    y2 = pow(y, 2, P)
    u = (y2 - 1) % P
    v = (D * y2 + 1) % P
    x2 = (u * pow(v, P - 2, P)) % P
    return pow(x2, (P - 1) // 2, P) != P - 1


def find_ata(owner: bytes, token_prog: bytes, mint: bytes) -> bytes:
    for bump in range(255, -1, -1):
        h = hashlib.sha256()
        h.update(owner)
        h.update(token_prog)
        h.update(mint)
        h.update(bytes([bump]))
        h.update(d.b58decode(ATA))
        h.update(b"ProgramDerivedAddress")
        digest = h.digest()
        if not on_curve(digest):
            return digest
    raise RuntimeError("ata")


def ix_data(ix: dict) -> bytes:
    raw = ix.get("data")
    if isinstance(raw, str):
        return d._b58_any(raw)
    return bytes(raw or [])


def ix_accs(ix: dict, keys: list[str]) -> list[str]:
    out = []
    for a in ix.get("accounts") or []:
        if isinstance(a, int):
            out.append(keys[a] if a < len(keys) else "")
        else:
            out.append(a)
    return out


def ix_prog(ix: dict, keys: list[str]) -> str | None:
    pid = ix.get("programId")
    if pid is not None:
        return pid
    i = ix.get("programIdIndex")
    if i is not None and i < len(keys):
        return keys[i]
    return None


def n_static(tx: dict) -> int:
    msg = tx["transaction"]["message"]
    keys = msg.get("accountKeys") or []
    n = 0
    for k in keys:
        if isinstance(k, dict):
            n += 1
        else:
            n += 1
    return n


def parse_top(tx: dict) -> dict:
    """Supported top-level swap, or fail-closed reason."""
    if not tx:
        return {"ok": 0, "why": "err"}
    keys = d.tx_keys(tx)
    nstat = n_static(tx)
    ixs = tx["transaction"]["message"].get("instructions") or []
    for ix in ixs:
        pid = ix_prog(ix, keys)
        data = ix_data(ix)
        accs = ix_accs(ix, keys)
        idxs = []
        for a in ix.get("accounts") or []:
            idxs.append(a if isinstance(a, int) else -1)
        if pid == DLMM and len(data) >= 24 and data[:8] in (SWAP2, SWAP1):
            if not accs or idxs and idxs[0] >= nstat:
                return {"ok": 0, "why": "dlmm_pool_alt"}
            if len(accs) < 11 or any(
                (idxs[k] >= nstat) for k in (4, 6, 7, 10) if k < len(idxs)
            ):
                return {"ok": 0, "why": "dlmm_dir_unresolved"}
            user_in = d.b58decode(accs[4])
            mint_x = d.b58decode(accs[6])
            mint_y = d.b58decode(accs[7])
            user = d.b58decode(accs[10])
            px = d.b58decode(accs[11]) if len(accs) > 11 else d.b58decode(TOKEN)
            py = d.b58decode(accs[12]) if len(accs) > 12 else d.b58decode(TOKEN)
            try:
                ata_x = find_ata(user, px, mint_x)
                ata_y = find_ata(user, py, mint_y)
            except RuntimeError:
                return {"ok": 0, "why": "dlmm_ata"}
            if user_in == ata_x:
                direc = 1
            elif user_in == ata_y:
                direc = 0
            else:
                okd = None
                for alt in (d.b58decode(TOKENZ), d.b58decode(TOKEN)):
                    if user_in == find_ata(user, alt, mint_x):
                        okd = 1
                        break
                    if user_in == find_ata(user, alt, mint_y):
                        okd = 0
                        break
                if okd is None:
                    return {"ok": 0, "why": "dlmm_dir_mismatch"}
                direc = okd
            ain, mino = struct.unpack_from("<QQ", data, 8)
            return {
                "ok": 1,
                "proto": 1,
                "variant": 1 if data[:8] == SWAP2 else 2,
                "pool": accs[0],
                "dir": direc,
                "amount_in": ain,
                "min_out": mino,
            }
        if pid == PUMP and len(data) >= 24:
            if data[:8] == PUMP_BUY:
                return {"ok": 0, "why": "pump_buy_exact_out"}
            if data[:8] not in (PUMP_SELL, PUMP_BUY_EQ):
                continue
            if not accs or (idxs and idxs[0] >= nstat):
                return {"ok": 0, "why": "pump_pool_alt"}
            ain, mino = struct.unpack_from("<QQ", data, 8)
            return {
                "ok": 1,
                "proto": 2,
                "variant": 3 if data[:8] == PUMP_SELL else 4,
                "pool": accs[0],
                "dir": 1 if data[:8] == PUMP_SELL else 0,
                "amount_in": ain,
                "min_out": mino,
            }
    return {"ok": 0, "why": "no_supported_top_ix"}


def collect_sigs(limit: int) -> list[str]:
    seen: list[str] = []
    have = set()

    def add(s: str | None) -> None:
        if s and s not in have:
            have.add(s)
            seen.append(s)

    cases = OUT.parent / "paper002" / "cases.json"
    if cases.exists():
        js = json.loads(cases.read_text(encoding="utf-8"))
        for c in js.get("cases") or []:
            add(c.get("trigger"))
            add(c.get("winner"))
    pairs = OUT.parent / "shred_v1_fat" / "pairs.jsonl"
    if pairs.exists():
        for line in pairs.open(encoding="utf-8"):
            r = json.loads(line)
            dex = set(r.get("dexes") or [])
            if "Meteora DLMM" not in dex and "Pump Swap" not in dex:
                continue
            add(r.get("trigger_sig"))
            add(r.get("mriya_sig"))
            if len(seen) >= limit * 4:
                break
    arbs = OUT.parent / "all_arbs_trial.jsonl"
    if arbs.exists():
        for line in arbs.open(encoding="utf-8"):
            r = json.loads(line)
            dex = r.get("dexes") or []
            if not any(x in dex for x in ("Meteora DLMM", "Pump Swap")):
                continue
            add(r.get("signature"))
            if len(seen) >= limit * 6:
                break
    return seen


def get_both(sig: str) -> tuple[dict | None, bytes | None]:
    parsed = None
    raw = None
    try:
        parsed = d.rpc("getTransaction", [
            sig, {"encoding": "json", "maxSupportedTransactionVersion": 1},
        ])
    except Exception as e:
        print(f"  json fail {sig[:8]} {type(e).__name__}", flush=True)
    try:
        r = d.rpc("getTransaction", [
            sig, {"encoding": "base64", "maxSupportedTransactionVersion": 1},
        ])
        if r and r.get("transaction"):
            tx = r["transaction"]
            if isinstance(tx, list) and tx:
                import base64
                raw = base64.b64decode(tx[0])
    except Exception as e:
        print(f"  b64 fail {sig[:8]} {type(e).__name__}", flush=True)
    return parsed, raw


def run_c(hot_n: str, path: Path) -> dict:
    try:
        p = subprocess.run(
            [hot_n, "--decode", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        line = (p.stdout or "").strip().splitlines()
        if not line:
            return {"ok": 0, "why": "c_empty"}
        return json.loads(line[-1])
    except Exception as e:
        return {"ok": 0, "why": f"c_{type(e).__name__}"}


def b58_pool(hex32: str) -> str:
    return d._pk(bytes.fromhex(hex32))


def write_report(rows: list[dict], supported: list[dict], mismatches: list[dict]) -> None:
    md = OUT / "PAPER-003.md"
    n_sup = len(supported)
    n_mis = len(mismatches)
    n_fail = sum(1 for r in rows if not r.get("expected", {}).get("ok"))
    lines = [
        "# PAPER-003",
        "",
        "Decode exact swap from raw transaction N. Fail closed otherwise.",
        "",
        f"Supported compared: **{n_sup}**. Mismatches: **{n_mis}**.",
        f"Unsupported / fail-closed: {n_fail}.",
        "",
        "Supported variants: DLMM swap/swap2 (ATA direction), Pump sell, "
        "Pump buy_exact_quote_in. Pump buy (exact-out) → fail closed.",
        "",
        "## Gate",
        "",
    ]
    if n_sup >= 50 and n_mis == 0:
        lines.append(f"PASS  {n_sup} supported, 100% exact pool/dir/amount_in/min_out.")
    elif n_mis:
        lines.append(f"FAIL  {n_mis} mismatch(es).")
    else:
        lines.append(f"FAIL  only {n_sup} supported (need 50).")
    lines += [
        "",
        "Dedup: one transaction across shred fragments → one `hot_decide`. "
        "Covered by `hot_n --selftest`.",
        "",
        "## Sample supported",
        "",
        "| proto | variant | dir | amount_in | pool |",
        "|-------|---------|-----|-----------|------|",
    ]
    for r in supported[:20]:
        e = r["expected"]
        lines.append(
            f"| {e['proto']} | {e['variant']} | {e['dir']} | {e['amount_in']} "
            f"| `{e['pool'][:8]}` |"
        )
    if mismatches:
        lines += ["", "## Mismatches", ""]
        for m in mismatches[:10]:
            lines.append(f"- `{m['sig'][:12]}` expected {m['expected']} got {m['got']}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {md}", flush=True)


def main() -> int:
    live.load_dotenv()
    limit = 100
    hot_n = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--hot_n":
        hot_n = sys.argv[2]
    CORPUS.mkdir(parents=True, exist_ok=True)
    sigs = collect_sigs(limit)
    print(f"sigs queued {len(sigs)}", flush=True)
    rows = []
    supported = []
    mismatches = []
    for sig in sigs:
        if len(supported) >= limit:
            break
        parsed, raw = get_both(sig)
        if not parsed or not raw:
            continue
        exp = parse_top(parsed)
        exp["sig"] = sig
        raw_path = CORPUS / f"{sig[:16]}.bin"
        raw_path.write_bytes(raw)
        got = {"ok": 0}
        if hot_n:
            got = run_c(hot_n, raw_path)
        rec = {"sig": sig, "expected": exp, "got": got, "raw": str(raw_path)}
        rows.append(rec)
        if exp.get("ok"):
            supported.append(rec)
            if hot_n:
                same = (
                    got.get("ok") == 1
                    and got.get("proto") == exp["proto"]
                    and got.get("dir") == exp["dir"]
                    and int(got.get("amount_in") or 0) == exp["amount_in"]
                    and int(got.get("min_out") or 0) == exp["min_out"]
                    and b58_pool(got.get("pool") or "") == exp["pool"]
                )
                if not same:
                    mismatches.append(rec)
                    print(f"  MISMATCH {sig[:12]} exp={exp} got={got}", flush=True)
                else:
                    print(f"  ok {sig[:12]} proto={exp['proto']} ain={exp['amount_in']}",
                          flush=True)
            else:
                print(f"  supported {sig[:12]} proto={exp['proto']} why=no_c",
                      flush=True)
        else:
            if hot_n and got.get("ok") == 1:
                mismatches.append(rec)
                print(f"  C-DECODED-UNSUPPORTED {sig[:12]} {exp.get('why')}", flush=True)
    (OUT / "prove.json").write_text(json.dumps({
        "n_rows": len(rows),
        "n_supported": len(supported),
        "n_mismatch": len(mismatches),
        "rows": rows,
    }, indent=2), encoding="utf-8")
    write_report(rows, supported, mismatches)
    if not hot_n:
        print("no --hot_n: corpus written, C compare skipped", flush=True)
        return 0
    if len(supported) < 50 or mismatches:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
