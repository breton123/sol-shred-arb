"""Complete pricing-dependency set for one liveuniv generation.

A pool is not state-ready until every account the quote/apply kernel
reads is in this set and has been subscribed. Control plane only.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "arb-cap"))
sys.path.insert(0, str(Path("/home/louis/arb-cap")))

import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

import submap as sm  # noqa: E402

PUMP = live.PUMP
DLMM = d.DLMM
FEE_CONFIG = "5PHirr8joyTMp9JMm6nW7hNDVyEYdkzDqazxPD7RaTjx"


def pump_global() -> str:
    return d._pk(d.find_pda([b"global_config"], d.b58decode(PUMP)))


def dlmm_oracle(pair: str) -> str:
    return d._pk(d.find_pda([b"oracle", d.b58decode(pair)], d.b58decode(DLMM)))


def _chunk_get(keys: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    uniq = [k for k in dict.fromkeys(keys) if k]
    for i in range(0, len(uniq), 80):
        chunk = uniq[i:i + 80]
        rows = d.get_multiple(chunk, retries=3)
        for pk, row in zip(chunk, rows):
            if row and row.get("data"):
                out[pk] = row
    return out


def bin_keys_for_active(pair: str, active_id: int) -> list[str]:
    keys = []
    for i in d.array_indexes(int(active_id)):
        keys.append(d.bin_array_pda(pair, i))
    return keys


def derive_pool(p: dict, fetched: dict[str, dict] | None = None) -> dict:
    """Return required + optional accounts for one univ pool."""
    kind = str(p.get("proto") or p.get("kind") or "")
    pk = p.get("pubkey") or p.get("pk")
    idx = int(p.get("idx") if p.get("idx") is not None else -1)
    required: list[tuple[str, str]] = []
    optional: list[tuple[str, str]] = []
    meta = {"idx": idx, "kind": kind, "pubkey": pk, "active_id": None,
            "vault_base": None, "vault_quote": None, "coin_creator": None}
    if not pk or idx < 0 or kind not in ("dlmm", "pump"):
        return {"required": required, "optional": optional, "meta": meta}

    raw = None
    if fetched and pk in fetched:
        raw = fetched[pk]["data"]

    if kind == "dlmm":
        required.append((pk, sm.ROLE_DLMM_PAIR))
        if raw:
            try:
                lb = d.parse_lbpair(raw)
            except Exception:
                lb = None
            if lb:
                meta["active_id"] = lb["active_id"]
                for bpk in bin_keys_for_active(pk, lb["active_id"]):
                    required.append((bpk, sm.ROLE_DLMM_BIN))
                optional.append((dlmm_oracle(pk), sm.ROLE_DLMM_ORACLE))
                mx = d._pk(lb["token_x"])
                my = d._pk(lb["token_y"])
                optional.append((mx, sm.ROLE_MINT))
                optional.append((my, sm.ROLE_MINT))
        else:
            snap = p.get("snap") or {}
            active = (snap.get("lb") or {}).get("active_id")
            if active is not None:
                meta["active_id"] = int(active)
                for bpk in bin_keys_for_active(pk, int(active)):
                    required.append((bpk, sm.ROLE_DLMM_BIN))
    else:
        required.append((pk, sm.ROLE_PUMP_POOL))
        required.append((pump_global(), sm.ROLE_PUMP_GLOBAL))
        required.append((FEE_CONFIG, sm.ROLE_PUMP_FEE_CONFIG))
        vb = vq = None
        if raw:
            parsed = live.parse_pump_pool(raw)
            if parsed:
                vb = live.b58e(parsed["vault_base"])
                vq = live.b58e(parsed["vault_quote"])
                required.append((d._pk(parsed["base"]), sm.ROLE_MINT))
                optional.append((d._pk(parsed["quote"]), sm.ROLE_MINT))
        if not vb:
            vb = p.get("vault_base") or p.get("vault_x")
        if not vq:
            vq = p.get("vault_quote") or p.get("vault_y")
        if isinstance(vb, str) and len(vb) > 20:
            required.append((vb, sm.ROLE_PUMP_VAULT_BASE))
            meta["vault_base"] = vb
        if isinstance(vq, str) and len(vq) > 20:
            required.append((vq, sm.ROLE_PUMP_VAULT_QUOTE))
            meta["vault_quote"] = vq
    return {"required": required, "optional": optional, "meta": meta}


def derive_generation(univ: dict) -> dict:
    """RPC-complete dependency map for the published universe generation."""
    pools = [p for p in (univ.get("pools") or [])
             if str(p.get("proto") or p.get("kind") or "") in ("dlmm", "pump")]
    pool_pks = [p.get("pubkey") or p.get("pk") for p in pools]
    fetched = _chunk_get([k for k in pool_pks if k])
    accounts: dict[str, list[dict]] = {}
    rows = []
    required_n = 0
    for p in pools:
        derv = derive_pool(p, fetched)
        idx = derv["meta"]["idx"]
        kind = derv["meta"]["kind"]
        req = derv["required"]
        # Second pass: if DLMM pair just fetched, bins are already in required.
        # If Pump pool fetched, vaults are in required. If still missing vaults/bins,
        # pool stays incomplete.
        for pk, role in req + derv["optional"]:
            accounts.setdefault(pk, []).append(
                {"pool_idx": idx, "role": role, "kind": kind,
                 "required": (pk, role) in req}
            )
        required_n += len(req)
        rows.append({
            "idx": idx,
            "kind": kind,
            "pubkey": derv["meta"]["pubkey"],
            "required": req,
            "optional": derv["optional"],
            "n_required": len(req),
            "active_id": derv["meta"]["active_id"],
            "vault_base": derv["meta"]["vault_base"],
            "vault_quote": derv["meta"]["vault_quote"],
        })
    return {
        "accounts": accounts,
        "pools": rows,
        "n_account": len(accounts),
        "n_required": required_n,
        "n_pool": len(rows),
        "univ_n": int(univ.get("n") or len(pools)),
    }
