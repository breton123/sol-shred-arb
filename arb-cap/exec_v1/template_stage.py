#!/usr/bin/env python3
"""Read-only template coverage for the oneshot plane and the hops plane.

Does not call hops_live deploy, sim7, or publish.
sim7 wraps 50_000_000 lamports and creates ATAs.
publish creates ATAs.
deploy upgrades a program.
inventory and size need the Frankfurt tree and were not run from this checkout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

V0_MAX = 1232


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def cover(path: Path) -> dict:
    doc = load(path)
    routes = doc.get("routes") or []
    oneshot = []
    for r in routes:
        raw = int(r.get("raw") or 0)
        oneshot.append({
            "dlmm": r.get("dlmm"),
            "pump": r.get("pump"),
            "seq": r.get("seq"),
            "tmpl0": bool(r.get("tmpl0")),
            "tmpl1": bool(r.get("tmpl1")),
            "RACE_READY": bool(r.get("RACE_READY")),
            "hops_race_ready": int(r.get("race_ready") or 0),
            "vector_ready": int(r.get("vector_ready") or 0),
            "size_ok": bool(r.get("size_ok")) and (raw == 0 or raw <= V0_MAX),
            "oversize": raw > V0_MAX,
        })
    return {
        "path": str(path),
        "exists": path.exists(),
        "routes": len(routes),
        "oneshot_ready": sum(
            1 for r in oneshot
            if r["RACE_READY"] and r["tmpl0"] and r["tmpl1"] and not r["oversize"]
        ),
        "hops_race_ready": sum(r["hops_race_ready"] for r in oneshot),
        "vector_ready": sum(r["vector_ready"] for r in oneshot),
        "oversize": sum(1 for r in oneshot if r["oversize"]),
        "rows": oneshot,
    }


def main(argv: list[str] | None = None) -> int:
    home = Path("/home/louis")
    paths = [
        home / "arb-exec/.deploy/alt_plane.json",
        home / "arb-cap/oneshot/ALT_PLANE.json",
        home / "arb-cap/fam6/hops_plane.json",
    ]
    if argv:
        paths = [Path(a) for a in argv]
    reports = [cover(p) for p in paths]
    out = Path(__file__).resolve().parent / "TEMPLATES.md"
    lines = [
        "# Route templates",
        "",
        "Read-only. No Custom(6) was simulated and no template was published in this run.",
        "",
        "Oneshot fires only rows with uppercase `RACE_READY`, `tmpl0`, and `tmpl1` "
        "(see `alt_plane.py`). `hops_live.py` publish sets lowercase `race_ready` "
        "from a prior Custom(6) and `vector_ready`. It does not write `tmpl0`/`tmpl1`, "
        "and it does not invent `RACE_READY`.",
        "",
        "Stages not run, and why:",
        "",
        "- `inventory`, `size` — need `/home/louis` univ, wallet RPC, and the hops program tree. **unverified** here.",
        "- `sim7` — calls `wrap_wsol(..., 50_000_000)` and `ensure_ata`. That moves SOL. Not run.",
        "- `publish` — creates missing ATAs. Not run.",
        "- `deploy` — program upgrade. Not run.",
        "",
        "A route0 pair is oneshot-executable only after `alt_plane.py` records a real "
        "compile of both directions. Setting `RACE_READY` by hand is not a step.",
        "",
    ]
    any_file = False
    for rep in reports:
        lines.append(f"## `{rep['path']}`")
        lines.append("")
        if not rep["exists"]:
            lines.append("Missing. **unverified**.")
            lines.append("")
            continue
        any_file = True
        lines.append(
            f"routes={rep['routes']} oneshot_ready={rep['oneshot_ready']} "
            f"hops_race_ready={rep['hops_race_ready']} vector_ready={rep['vector_ready']} "
            f"oversize={rep['oversize']}"
        )
        lines.append("")
    if not any_file:
        lines.append("No plane file was present, so coverage is **unverified** and no pair was staged.")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
