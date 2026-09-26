#!/usr/bin/env python3
"""Label quote-mint credits from cached PUMP-FEE-014 txs. Jupiter-wrapped Pump."""
from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from reduce_buy013 import collect, pred_buy_quote
from reduce_fee014 import quote_deltas, rpc
from replay import _dir_amt


def main() -> None:
    root = Path("/data/bsc/captures/soak_fastsoak_20260925")
    u = json.loads(Path("/home/louis/captures/paper_orbit/liveuniv.json").read_text())
    meta = {int(p["idx"]): p for p in u.get("pools") or []}
    vault_q = {}
    for p in u.get("pools") or []:
        vault_q[int(p["idx"])] = p.get("vy") or p.get("vault_y") or p.get("quote_vault")
    buys, _ = collect(root / "state008/mismatch", meta)
    by_sig = {}
    for b in buys:
        hx = b.get("trigger_sig") or b.get("sig")
        if hx:
            by_sig[hx] = b

    dest_n = Counter()
    dest_amt = defaultdict(int)
    dest_role = {}
    triples = Counter()
    closed = 0
    n = 0
    residual_eq_extra = 0
    examples = []
    for fp in (root / "fee014_tx").glob("*.json"):
        hx = fp.stem
        b = by_sig.get(hx)
        if not b:
            continue
        idx = int(b["idx"])
        p = meta.get(idx) or {}
        qmint = p.get("my") or p.get("mx")
        vault = vault_q.get(idx)
        for w in b.get("staged_writes") or []:
            if w.get("role") == "pump_vault_quote":
                vault = w.get("pubkey")
                break
        tx = json.loads(fp.read_text())
        d = quote_deltas(tx, qmint)
        if not d:
            continue
        _, ain = _dir_amt(b)
        pred, fees = pred_buy_quote(b["s_before"], ain)
        pub = int(b["published_s"]["reserve_quote"]) - int(b["s_before"]["reserve_quote"])
        leave = pred - pub
        credits = [(pk, am) for pk, am in d.items() if am > 0]
        debits = [(pk, -am) for pk, am in d.items() if am < 0]
        credits.sort(key=lambda x: -x[1])
        user_spend = sum(a for _, a in debits)
        cred_sum = sum(a for _, a in credits)
        n += 1
        if user_spend == cred_sum:
            closed += 1
        extra = 0
        fee_accs = []
        for pk, am in credits:
            dest_n[pk] += 1
            dest_amt[pk] += am
            if vault and pk == vault:
                dest_role[pk] = "pool_quote_vault"
            elif am == pub and dest_role.get(pk) != "pool_quote_vault":
                dest_role.setdefault(pk, "pool_quote_vault?")
            else:
                dest_role.setdefault(pk, "fee_or_other")
                extra += am
                fee_accs.append((pk[:8], am))
        if extra == leave:
            residual_eq_extra += 1
        triples[tuple(sorted(pk[:8] for pk, am in credits if pk != vault))] += 1
        if len(examples) < 6:
            examples.append({
                "idx": idx, "ain": ain, "vault": pub, "pred": pred, "leave": leave,
                "user_spend": user_spend, "credits": credits[:6],
                "extra": extra, "extra_eq_leave": extra == leave,
                "fees_kernel": fees,
            })

    url = os.environ.get("HELIUS_RPC_URL")
    owners = {}
    top = [pk for pk, _ in dest_n.most_common(12)]
    if url and top:
        vals = rpc(url, "getMultipleAccounts", [top, {"encoding": "jsonParsed"}])
        for pk, acc in zip(top, (vals or {}).get("value") or []):
            if not acc:
                continue
            parsed = ((acc.get("data") or {}) if isinstance(acc.get("data"), dict) else None)
            info = (acc.get("data") or {})
            if isinstance(info, dict):
                parsed = info.get("parsed") or info
            owner = None
            mint = None
            if isinstance(parsed, dict):
                info2 = parsed.get("info") or parsed
                owner = info2.get("owner") if isinstance(info2, dict) else None
                mint = info2.get("mint") if isinstance(info2, dict) else None
            owners[pk] = {"owner": owner, "mint": mint, "owner_acc": acc.get("owner")}

    doc = {
        "n_tx": n,
        "conservation_closed": closed,
        "extra_credits_eq_residual": residual_eq_extra,
        "dest_n": dest_n.most_common(12),
        "dest_role": dest_role,
        "owners": owners,
        "fee_set": triples.most_common(8),
        "examples": examples,
    }
    Path("/data/bsc/captures/soak_fastsoak_20260925/PUMP014_XFER.json").write_text(
        json.dumps(doc, indent=2) + "\n"
    )
    print(json.dumps({
        "n_tx": n, "closed": closed, "extra_eq_leave": residual_eq_extra,
        "dest": dest_n.most_common(8), "owners": {k[:8]: v for k, v in owners.items()},
        "fee_set": triples.most_common(5),
        "ex0": examples[0] if examples else None,
    }, indent=2))


if __name__ == "__main__":
    main()
