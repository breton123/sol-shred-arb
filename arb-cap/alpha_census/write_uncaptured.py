#!/usr/bin/env python3
"""Build UNCAPTURED.jsonl from the reclassified sample. Gross stays null."""
import json
from collections import Counter
from pathlib import Path

OUT = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\alpha_census")
rows = [json.loads(l) for l in (OUT / "joined2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
keep = [
    r for r in rows
    if r["trigger_class"] not in ("swap", "no_invoke") and r["taker"] == "NO_MINT_MATCH"
]

def preexec(cls: str) -> str:
    if cls == "liquidity":
        return "PREEXEC_DETERMINISTIC_WITH_STATE"
    if cls in ("fee_config", "admin_state", "lifecycle", "other"):
        return "PREEXEC_PARTIAL"
    if cls == "swap+liquidity":
        return "PREEXEC_PARTIAL"
    return "UNKNOWN"

out_rows = []
for r in keep:
    out_rows.append({
        "signature": r["signature"],
        "slot": r["slot"],
        "trigger_class": r["trigger_class"],
        "outer_program": None,
        "affected_pools": None,
        "affected_tokens": r.get("mints") or [],
        "route": None,
        "hop_count": None,
        "edge_before": None,
        "edge_after": None,
        "actual_size_gross": None,
        "optimal_gross": None,
        "optimal_size": None,
        "lifetime": None,
        "subsequent_taker": "NO_MINT_MATCH_WITHIN_5_SLOTS",
        "known_searcher": None,
        "preexec_predictability": preexec(r["trigger_class"]),
        "state_confidence": "STATE_UNAVAILABLE",
        "instructions": r.get("instructions") or [],
        "program": r.get("program"),
        "note": "Not a measured edge. No S_before/S_after. Do not sum gross.",
    })
out_rows.sort(key=lambda r: (r["trigger_class"], r["signature"] or ""))
(OUT / "UNCAPTURED.jsonl").write_text(
    "".join(json.dumps(r) + "\n" for r in out_rows),
    encoding="utf-8",
)
print("rows", len(out_rows))
print(Counter((r["program"], r["trigger_class"]) for r in out_rows))
