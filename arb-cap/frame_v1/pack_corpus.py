#!/usr/bin/env python3
"""Materialize the permanent 590-winner v1 corpus + legacy/v0 controls."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from parse import parse_any, parse_legacy_v0, wire_kind

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
META = HERE / "winners.jsonl"
CORPUS = HERE / "corpus"
IDX = HERE / "corpus.jsonl"


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    (CORPUS / "v1").mkdir(exist_ok=True)
    (CORPUS / "control").mkdir(exist_ok=True)
    rows = []
    for line in META.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    out = []
    n_v0 = n_leg = 0
    for r in rows:
        src = RAW / (r["sig"] + ".bin")
        if not src.exists():
            continue
        raw = src.read_bytes()
        kind = r.get("kind") or wire_kind(raw)
        dest_dir = CORPUS / ("v1" if kind == "v1" else "control")
        if kind != "v1":
            if kind == "v0" and n_v0 >= 8:
                continue
            if kind == "legacy" and n_leg >= 4:
                continue
            if kind == "v0":
                n_v0 += 1
            if kind == "legacy":
                n_leg += 1
        dest = dest_dir / (r["sig"] + ".bin")
        shutil.copy2(src, dest)
        pre = parse_legacy_v0(raw)
        post = parse_any(raw)
        out.append({
            "sig": r["sig"],
            "usd": r.get("usd"),
            "slot": r.get("slot"),
            "kind": kind,
            "n": len(raw),
            "before": pre.get("klass"),
            "after": post.get("klass"),
            "nkeys": post.get("nkeys"),
            "ninstr": post.get("ninstr"),
        })
    IDX.write_text("\n".join(json.dumps(x) for x in out) + "\n", encoding="utf-8")
    print("corpus", len(out), "v1", sum(1 for x in out if x["kind"] == "v1"))


if __name__ == "__main__":
    main()
