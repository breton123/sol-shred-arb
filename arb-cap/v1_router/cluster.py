#!/usr/bin/env python3
"""V1-ROUTER-001 — offline clustering + held-out symbolic freeze.

Does not invent inner CPI from the packet. JSON meta is a label only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "arb-cap" / "frame_v1"))
sys.path.insert(0, str(ROOT / "arb-cap" / "trigger011"))
from b58 import b58decode, b58encode as _b58encode  # noqa: E402


def b58encode(raw: bytes) -> str:
    if raw == b"\x00" * 32:
        return "11111111111111111111111111111111"
    return _b58encode(raw)
from parse import (  # noqa: E402
    PROG_DLMM,
    PROG_PUMP,
    classify_ixs,
    parse_any,
)

HERE = Path(__file__).resolve().parent
META = ROOT / "arb-cap" / "frame_v1" / "winners.jsonl"
RAW = ROOT / "arb-cap" / "frame_v1" / "raw"
JSON = HERE / "txjson"
POOLS = ROOT / "arb-cap" / "trigger012" / "required_pools.json"
UNIV = ROOT / "arb-cap" / "regress" / "liveuniv_now.json"
OUT = HERE

INFRA = {
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "AddressLookupTab1e1111111111111111111111111",
}
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PUMP_SELL = bytes.fromhex("33e685a4017f83ad")
PUMP_BUY_EQ = bytes.fromhex("c62e1552b4d9e870")
PUMP_BUY = bytes.fromhex("66063d1201daebea")
DLMM_SWAP2 = bytes.fromhex("414b3f4ceb5b5b88")
DLMM_SWAP1 = bytes.fromhex("f8c69e91e17587c8")
DEX_DISC = {
    PUMP_SELL: "pump_sell",
    PUMP_BUY_EQ: "pump_buy_eq",
    PUMP_BUY: "pump_buy_xo",
    DLMM_SWAP2: "dlmm_swap2",
    DLMM_SWAP1: "dlmm_swap1",
}


def holdout(sig: str) -> bool:
    return hashlib.sha256(sig.encode()).digest()[-1] % 5 == 0


def load_known_pools() -> dict[str, str]:
    out = {}
    if POOLS.exists():
        doc = json.loads(POOLS.read_text(encoding="utf-8"))
        for p in doc.get("pools") or []:
            if p.get("pool"):
                out[p["pool"]] = p.get("proto") or "unknown"
    if UNIV.exists():
        doc = json.loads(UNIV.read_text(encoding="utf-8"))
        for row in doc.get("picked") or []:
            for pk in row.get("pks") or []:
                out.setdefault(pk, "univ")
    return out


def roles(nsig: int, nkeys: int, parsed: dict) -> dict:
    """v1 header is the same signer/readonly split as legacy."""
    raw = parsed.get("_hdr") or {}
    ro_s = raw.get("ro_s", 0)
    ro_u = raw.get("ro_u", 0)
    wr_s = max(nsig - ro_s, 0)
    wr_u = max(nkeys - nsig - ro_u, 0)
    return {
        "wr_s": wr_s,
        "ro_s": ro_s,
        "wr_u": wr_u,
        "ro_u": ro_u,
        "pat": f"ws{wr_s}/rs{ro_s}/wu{wr_u}/ru{ro_u}",
    }


def attach_header(raw: bytes, parsed: dict) -> None:
    if parsed.get("ver") != "v1" or len(raw) < 4:
        parsed["_hdr"] = {"ro_s": 0, "ro_u": 0}
        return
    parsed["_hdr"] = {"ro_s": raw[2], "ro_u": raw[3]}


def router_ixs(parsed: dict) -> list[dict]:
    keys = parsed.get("keys") or []
    out = []
    for ix in parsed.get("ixs") or []:
        if ix["prog"] >= len(keys):
            continue
        pk = b58encode(keys[ix["prog"]])
        if pk in INFRA:
            continue
        data = ix["data"]
        out.append({
            "program": pk,
            "dex": pk in (DLMM, PUMP),
            "disc": data[:8].hex() if len(data) >= 8 else data.hex(),
            "data_len": len(data),
            "nacct": len(ix["acc"]),
            "acc": ix["acc"],
            "data": data,
        })
    return out


def u64s(data: bytes) -> list[int]:
    vals = []
    for i in range(0, max(len(data) - 7, 0)):
        v = int.from_bytes(data[i:i + 8], "little")
        if 0 < v < (1 << 62):
            vals.append(v)
    return vals


def label_ops(doc: dict | None) -> list[dict]:
    if not doc or doc.get("_error"):
        return []
    msg = (doc.get("transaction") or {}).get("message") or {}
    meta = doc.get("meta") or {}
    keys = []
    for k in msg.get("accountKeys") or []:
        if isinstance(k, str):
            keys.append(k)
        elif isinstance(k, dict) and k.get("pubkey"):
            keys.append(k["pubkey"])
    loaded = meta.get("loadedAddresses") or {}
    for side in ("writable", "readonly"):
        for k in loaded.get(side) or []:
            keys.append(k if isinstance(k, str) else (k.get("pubkey") or ""))
    ops = []

    def walk(ix, where):
        pid = ix.get("programId")
        if pid is None:
            idx = ix.get("programIdIndex")
            if isinstance(idx, int) and idx < len(keys):
                pid = keys[idx]
        if pid not in (DLMM, PUMP):
            return
        data_s = ix.get("data") or ""
        raw = b""
        if data_s:
            try:
                raw = b58decode(data_s)
            except Exception:
                raw = b""
        accs = []
        for a in ix.get("accounts") or []:
            if isinstance(a, int) and a < len(keys):
                accs.append(keys[a])
            elif isinstance(a, str):
                accs.append(a)
        disc = raw[:8]
        ops.append({
            "where": where,
            "proto": "pump" if pid == PUMP else "dlmm",
            "pool": accs[0] if accs else None,
            "amount_in": int.from_bytes(raw[8:16], "little") if len(raw) >= 16 else None,
            "disc": DEX_DISC.get(disc),
            "direction": (
                "base_to_quote" if disc == PUMP_SELL else
                "quote_to_base" if disc in (PUMP_BUY_EQ, PUMP_BUY) else
                "dlmm" if disc in (DLMM_SWAP2, DLMM_SWAP1) else None
            ),
        })

    for ix in msg.get("instructions") or []:
        walk(ix, "outer")
    for g in meta.get("innerInstructions") or []:
        for ix in g.get("instructions") or []:
            walk(ix, "inner")
    return ops


def mint_flags(keys_b58: list[str], doc: dict | None) -> str:
    flags = []
    if WSOL in keys_b58:
        flags.append("wsol")
    if USDC in keys_b58:
        flags.append("usdc")
    mints = set()
    if doc:
        meta = doc.get("meta") or {}
        for bal in (meta.get("preTokenBalances") or []) + (meta.get("postTokenBalances") or []):
            m = bal.get("mint")
            if m:
                mints.add(m)
    if WSOL in mints:
        flags.append("m_wsol")
    if USDC in mints:
        flags.append("m_usdc")
    extra = len([m for m in mints if m not in (WSOL, USDC)])
    if extra:
        flags.append(f"m_other{extra}")
    return "+".join(flags) or "none"


def analyze_one(sig: str, usd: float, raw: bytes, known: dict[str, str], doc: dict | None) -> dict:
    parsed = parse_any(raw)
    attach_header(raw, parsed)
    if parsed.get("klass") != "framed" or parsed.get("ver") != "v1":
        return {"sig": sig, "klass": "not_v1"}
    keys = [b58encode(k) for k in parsed["keys"]]
    ixs = router_ixs(parsed)
    cls = classify_ixs(parsed)
    dex_outer = [x for x in ixs if x["dex"]]
    routers = [x for x in ixs if not x["dex"]]
    kind = "direct" if dex_outer and not routers else ("mixed" if dex_outer and routers else "router")
    primary = (dex_outer or routers or [{"program": "none", "disc": "", "data_len": 0, "nacct": 0, "data": b""}])[0]
    pools = [k for k in keys if k in known]
    role = roles(parsed["nsig"], parsed["nkeys"], parsed)
    blob = b"".join(x["data"] for x in ixs)
    ops = label_ops(doc)
    inner = [o for o in ops if o["where"] == "inner"]
    amts = [o["amount_in"] for o in inner if o.get("amount_in")]
    found = 0
    for a in amts:
        if a.to_bytes(8, "little") in blob:
            found += 1
    if not amts:
        locus = "no_inner_label"
    elif found == len(amts):
        locus = "amount_in_outer_bytes"
    elif found:
        locus = "partial_amount_in_outer"
    else:
        locus = "amount_absent_from_outer"
    label_pools = [o["pool"] for o in inner if o.get("pool")]
    pools_from_inline = [p for p in label_pools if p in keys]
    dirs = {o["direction"] for o in inner if o.get("direction")}
    can_pool = bool(pools) or (bool(label_pools) and len(pools_from_inline) == len(set(label_pools)))
    # Prediction inputs: inline ∩ known, or every labeled pool is in the address array.
    can_pool_pred = bool(pools) or (bool(label_pools) and set(label_pools) <= set(keys))
    can_dir = False
    if len(dirs) == 1 and kind == "direct":
        can_dir = True
    can_in = locus == "amount_in_outer_bytes"
    can_out_prev = False
    if len(amts) >= 2 and found == len(amts):
        can_out_prev = True
    can_inverse = can_pool_pred and can_dir and can_in
    can_term = can_inverse
    mint = mint_flags(keys, None)
    shape = "|".join([
        primary["program"],
        primary["disc"][:16],
        str(primary["data_len"]),
        role["pat"],
        mint,
    ])
    return {
        "sig": sig,
        "usd": usd,
        "n": len(raw),
        "kind": kind,
        "holdout": holdout(sig),
        "outer": primary["program"],
        "disc": primary["disc"],
        "data_len": primary["data_len"],
        "nacct": primary["nacct"],
        "nkeys": parsed["nkeys"],
        "ninstr": parsed["ninstr"],
        "mask": parsed.get("mask"),
        "writable": role["pat"],
        "shape": shape,
        "pools_inline": pools,
        "n_known_pools": len(pools),
        "mint": mint_flags(keys, doc),
        "mint_wire": mint,
        "stage_wire": cls["stage"],
        "dex_static": cls["dex_static"],
        "locus": locus,
        "n_inner": len(inner),
        "label_pools": label_pools,
        "label_dirs": sorted(d for d in dirs if d),
        "can": {
            "pools": can_pool_pred,
            "direction": can_dir,
            "input_expression": can_in,
            "output_previous_leg": can_out_prev,
            "balance_delta": False,
            "inverse_quote": can_inverse,
            "terminal_state": can_term,
        },
    }


def freeze_shape(rows: list[dict]) -> dict:
    train = [r for r in rows if not r["holdout"]]
    hold = [r for r in rows if r["holdout"]]
    def frac(xs, pred):
        if not xs:
            return None
        return sum(1 for x in xs if pred(x)) / len(xs)

    def field(name):
        tr = frac(train, lambda r: r["can"][name])
        ho = frac(hold, lambda r: r["can"][name])
        exact = (
            tr == 1.0 and ho == 1.0 and len(hold) >= 2 and len(train) >= 4
        )
        bounded = (tr or 0) >= 0.8 and name in ("pools",)
        return {"train": tr, "holdout": ho, "n_train": len(train), "n_hold": len(hold), "exact": exact, "bounded": bounded and not exact}

    fields = {k: field(k) for k in (
        "pools", "direction", "input_expression", "output_previous_leg",
        "balance_delta", "inverse_quote", "terminal_state",
    )}
    loci = Counter(r["locus"] for r in rows)
    if fields["input_expression"]["exact"] and fields["pools"]["exact"]:
        verdict = "symbolic_exact"
    elif fields["pools"]["exact"] or fields["pools"]["bounded"]:
        verdict = "symbolic_bounded"
    else:
        verdict = "unknown"
    return {"fields": fields, "loci": dict(loci), "verdict": verdict}


def main():
    known = load_known_pools()
    rows = []
    for line in META.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("kind") != "v1":
            continue
        raw_p = RAW / (rec["sig"] + ".bin")
        if not raw_p.exists():
            continue
        raw = raw_p.read_bytes()
        jp = JSON / (rec["sig"] + ".json")
        doc = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else None
        rows.append(analyze_one(rec["sig"], float(rec.get("usd") or 0), raw, known, doc))

    routers = [r for r in rows if r.get("kind") == "router"]
    direct = [r for r in rows if r.get("kind") == "direct"]
    by_shape = defaultdict(list)
    by_outer = defaultdict(list)
    for r in routers:
        by_shape[r["shape"]].append(r)
        by_outer[r["outer"]].append(r)

    shapes = []
    for sk, xs in sorted(by_shape.items(), key=lambda kv: -sum(r["usd"] for r in kv[1])):
        fr = freeze_shape(xs)
        shapes.append({
            "shape": sk,
            "outer": xs[0]["outer"],
            "disc": xs[0]["disc"],
            "data_len": xs[0]["data_len"],
            "nacct": xs[0]["nacct"],
            "nkeys": xs[0]["nkeys"],
            "mask": xs[0]["mask"],
            "writable": xs[0]["writable"],
            "n": len(xs),
            "usd": sum(r["usd"] for r in xs),
            "example": xs[0]["sig"],
            **fr,
        })

    outers = []
    for pk, xs in sorted(by_outer.items(), key=lambda kv: -sum(r["usd"] for r in kv[1])):
        verdicts = Counter(freeze_shape(by_shape[r["shape"]])["verdict"] for r in xs)
        outers.append({
            "outer": pk,
            "n": len(xs),
            "usd": sum(r["usd"] for r in xs),
            "unique_shapes": len({r["shape"] for r in xs}),
            "prediction_coverage": {
                "symbolic_exact": verdicts.get("symbolic_exact", 0),
                "symbolic_bounded": verdicts.get("symbolic_bounded", 0),
                "unknown": verdicts.get("unknown", 0),
            },
        })

    telem = {
        "v1_router_total": len(routers),
        "v1_direct": len(direct),
        "v1_shape_known": sum(s["n"] for s in shapes if s["verdict"] != "unknown"),
        "v1_symbolic_exact": sum(s["n"] for s in shapes if s["verdict"] == "symbolic_exact"),
        "v1_symbolic_bounded": sum(s["n"] for s in shapes if s["verdict"] == "symbolic_bounded"),
        "v1_unknown": sum(s["n"] for s in shapes if s["verdict"] == "unknown"),
        "v1_router_usd": sum(r["usd"] for r in routers),
        "labels": sum(1 for r in routers if r["locus"] != "no_inner_label"),
        "holdout": sum(1 for r in routers if r["holdout"]),
        "locus": dict(Counter(r["locus"] for r in routers)),
        "n_gt_1232": sum(1 for r in routers if r["n"] > 1232),
        "n_max": max((r["n"] for r in routers), default=0),
    }
    report = {
        "telemetry": telem,
        "outers": outers,
        "shapes": shapes[:80],
        "n_shapes": len(shapes),
        "direct": [{"sig": d["sig"], "usd": d["usd"], "outer": d["outer"]} for d in direct],
        "frozen_exact": [s for s in shapes if s["verdict"] == "symbolic_exact"],
    }
    (OUT / "dashboard.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (OUT / "shapes.jsonl").write_text(
        "\n".join(json.dumps(s) for s in shapes) + "\n", encoding="utf-8")
    (OUT / "rows.jsonl").write_text(
        "\n".join(json.dumps({k: v for k, v in r.items() if k != "data"}) for r in rows) + "\n",
        encoding="utf-8")
    print(json.dumps(telem, indent=2))
    print("outers", len(outers), "shapes", len(shapes), "frozen_exact", len(report["frozen_exact"]))
    for o in outers[:12]:
        print(f"  {o['n']:4d} ${o['usd']:8.1f}  shapes={o['unique_shapes']:3d}  {o['outer'][:32]}")


if __name__ == "__main__":
    main()
