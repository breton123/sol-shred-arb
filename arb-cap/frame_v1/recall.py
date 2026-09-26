#!/usr/bin/env python3
"""Historical winner recall before/after FRAME-V1 + downstream stage."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from parse import classify_ixs, parse_any, parse_legacy_v0, wire_kind

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
META = HERE / "winners.jsonl"
UNIV = HERE.parents[1] / "regress" / "liveuniv_now.json"
OUT = HERE / "recall.json"


def watched_keys() -> set[bytes]:
    if not UNIV.exists():
        return set()
    doc = json.loads(UNIV.read_text(encoding="utf-8"))
    out = set()
    pools = doc.get("pools") or doc.get("live") or []
    if isinstance(doc, list):
        pools = doc
    for p in pools:
        if not isinstance(p, dict):
            continue
        for k in ("pool", "vault_x", "vault_y", "token_x", "token_y"):
            v = p.get(k)
            if isinstance(v, str) and len(v) >= 32:
                pass
        raw = p.get("pool_bytes") or p.get("pk")
        if isinstance(raw, str) and len(raw) == 64:
            try:
                out.add(bytes.fromhex(raw))
            except ValueError:
                pass
    return out


def load_meta():
    rows = []
    if META.exists():
        for line in META.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main():
    rows = load_meta()
    before = Counter()
    after = Counter()
    kinds = Counter()
    stages = Counter()
    stages_v1 = Counter()
    watch_hit = Counter()
    usd = {"v1_total": 0.0, "v1_framed": 0.0, "all": 0.0, "framed_after": 0.0}
    v1_n = {"total": 0, "framed": 0, "incomplete": 0, "invalid": 0}
    samples = []
    watch = watched_keys()

    for r in rows:
        sig = r["sig"]
        path = RAW / (sig + ".bin")
        raw = path.read_bytes() if path.exists() else b""
        kind = r.get("kind") or wire_kind(raw)
        kinds[kind] += 1
        usd["all"] += float(r.get("usd") or 0)
        pre = parse_legacy_v0(raw) if raw else {"klass": "absent", "why": "missing"}
        post = parse_any(raw) if raw else {"klass": "absent", "why": "missing"}
        before[pre.get("klass") or "absent"] += 1
        after[post.get("klass") or "absent"] += 1
        if kind == "v1":
            v1_n["total"] += 1
            usd["v1_total"] += float(r.get("usd") or 0)
            k = post.get("klass")
            if k == "framed":
                v1_n["framed"] += 1
                usd["v1_framed"] += float(r.get("usd") or 0)
            elif k == "incomplete":
                v1_n["incomplete"] += 1
            else:
                v1_n["invalid"] += 1
        if post.get("klass") == "framed":
            usd["framed_after"] += float(r.get("usd") or 0)
            cls = classify_ixs(post)
            stages[cls["stage"]] += 1
            if kind == "v1":
                stages_v1[cls["stage"]] += 1
            keys = post.get("keys") or []
            hit = bool(watch) and any(k in watch for k in keys)
            watch_hit["hit" if hit else "miss"] += 1
            if kind == "v1":
                samples.append({
                    "sig": sig,
                    "usd": r.get("usd"),
                    "n": len(raw),
                    "stage": cls["stage"],
                    "n_exact": cls["n_exact"],
                    "dex_static": cls["dex_static"],
                    "watched": hit,
                })

    report = {
        "n": len(rows),
        "kinds": dict(kinds),
        "before": dict(before),
        "after": dict(after),
        "v1": v1_n,
        "usd": usd,
        "downstream": dict(stages),
        "downstream_v1": dict(stages_v1),
        "watched": dict(watch_hit),
        "winner_recall": {
            "before_framed": before.get("framed", 0),
            "after_framed": after.get("framed", 0),
            "before_pct": round(100.0 * before.get("framed", 0) / max(len(rows), 1), 2),
            "after_pct": round(100.0 * after.get("framed", 0) / max(len(rows), 1), 2),
        },
        "v1_samples_head": samples[:12],
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
