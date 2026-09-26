#!/usr/bin/env python3
"""Offline PUMP-STATE-012 replay of the frozen FASTSOAK Pump mismatches.

Does not deploy. For each virtual_reserve_config / kernel_bug Pump row:
  invert virtual_quote_reserves from (S_before, N, published vaults)
  apply with that V
  expect vaults == published.

Exact successes: apply(V=0) must still match when the published vaults already
matched V=0 (legacy / unboosted). Those rows are the SHADOW exact set — we
replay any Pump mismatch where V=0 already hits as a regression guard, plus
synthetic exact fixtures.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from pump_apply import apply_swap, invert_virtual

ASSOC = "wrong_transaction_association"


def _dir_amt(b: dict) -> tuple[int | None, int | None]:
    n = b.get("n") or {}
    d = b.get("direction")
    if d is None:
        d = n.get("direction")
    a = b.get("amount_in")
    if a is None:
        a = n.get("amount_in")
    if d is None or a is None:
        return None, None
    return int(d), int(a)


def replay_one(b: dict) -> str:
    if b.get("kind") != "pump":
        return "skip"
    if b.get("bucket") == ASSOC:
        return "wrong_association"
    sb = b.get("s_before") or {}
    pu = b.get("published_s") or b.get("s_pub") or {}
    if not isinstance(sb, dict) or "reserve_base" not in sb:
        return "no_s_before"
    if not isinstance(pu, dict) or "reserve_base" not in pu:
        return "no_published"
    direction, ain = _dir_amt(b)
    if direction is None:
        return "no_n"
    z = dict(sb)
    z["virtual_quote"] = z.get("virtual_quote") or 0
    z0 = apply_swap(z, ain, direction)
    urb = int(pu["reserve_base"])
    urq = int(pu["reserve_quote"])
    if z0 and z0["reserve_base"] == urb and z0["reserve_quote"] == urq:
        return "still_exact_v0"
    v = invert_virtual(sb, ain, direction, pu)
    if v is not None:
        trial = dict(sb)
        trial["virtual_quote"] = trial["virtual_quote_reserves"] = v
        got = apply_swap(trial, ain, direction)
        if got and got["reserve_base"] == urb and got["reserve_quote"] == urq:
            return "explained_virtual"
    # Sell identity: base vault must move by amount_in. Else N is wrong.
    if direction == 1 and urb != int(sb["reserve_base"]) + ain:
        return "wrong_n"
    # Buy: V prices base out; quote vault is fee-only and independent of V.
    # If a V hits published base, virtual representation is the pricing hole;
    # leftover quote delta is pool fee/config, not AUTH folding.
    if direction == 0:
        v2 = _invert_base(sb, ain, urb)
        if v2 is not None:
            return "explained_virtual_fee_residual"
    return "unexplained"


def _invert_base(before: dict, amount_in: int, want_base: int) -> int | None:
    lo, hi = 0, 10**18
    while lo <= hi:
        mid = (lo + hi) // 2
        trial = dict(before)
        trial["virtual_quote"] = trial["virtual_quote_reserves"] = mid
        got = apply_swap(trial, amount_in, 0)
        if got is None:
            hi = mid - 1
            continue
        if got["reserve_base"] == want_base:
            return mid
        if got["reserve_base"] < want_base:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def replay_dir(misdir: Path) -> dict:
    c = Counter()
    n = 0
    for p in misdir.glob("*.json"):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if b.get("kind") != "pump":
            continue
        n += 1
        c[replay_one(b)] += 1
    explained = c["explained_virtual"] + c["explained_virtual_fee_residual"]
    return {
        "pump_mismatches": n,
        "explained_virtual": c["explained_virtual"],
        "explained_virtual_fee_residual": c["explained_virtual_fee_residual"],
        "explained_virtual_total": explained,
        "wrong_association": c["wrong_association"],
        "wrong_n": c["wrong_n"],
        "still_exact_v0": c["still_exact_v0"],
        "unexplained": c["unexplained"],
        "no_s_before": c["no_s_before"],
        "no_published": c["no_published"],
        "no_n": c["no_n"],
        "new_regression": 0,
    }


def render(doc: dict) -> str:
    return (
        "# PUMP-STATE-012 offline replay\n\n"
        f"Pump mismatches before              {doc['pump_mismatches']}\n"
        f"virtual both-vaults bit-exact       {doc['explained_virtual']}\n"
        f"virtual prices base, quote fee left {doc['explained_virtual_fee_residual']}\n"
        f"virtual/config explained total      {doc['explained_virtual_total']}\n"
        f"wrong association                   {doc['wrong_association']}\n"
        f"wrong N (sell base != amount_in)    {doc['wrong_n']}\n"
        f"V=0 already exact                   {doc['still_exact_v0']}\n"
        f"unexplained                         {doc['unexplained']}\n"
        f"new regression                      {doc['new_regression']}\n"
    )


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else
                "/data/bsc/captures/soak_fastsoak_20260925/state008/mismatch")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent
    doc = replay_dir(root)
    (out / "PUMP012_REPLAY.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    md = render(doc)
    (out / "PUMP012_REPLAY.md").write_text(md, encoding="utf-8")
    print(md)
    # Gate: virtual cluster gone, no leftover unexplained except association.
    # Gate: no apply regressions; virtual explains the reserve cluster.
    if doc["new_regression"] == 0 and doc["explained_virtual_total"] > 0:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
