"""liveuniv → account_pubkey → [(pool_idx, role)]. Control plane only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

UNIV = Path("/home/louis/captures/paper_orbit/liveuniv.json")

ROLE_DLMM_PAIR = "dlmm_lbpair"
ROLE_DLMM_BIN = "dlmm_binarray"
ROLE_DLMM_ORACLE = "dlmm_oracle"
ROLE_PUMP_POOL = "pump_pool"
ROLE_PUMP_VAULT_BASE = "pump_vault_base"
ROLE_PUMP_VAULT_QUOTE = "pump_vault_quote"
ROLE_PUMP_GLOBAL = "pump_global"
ROLE_PUMP_FEE_CONFIG = "pump_fee_config"
ROLE_MINT = "mint"
# Reserved for later venues — same map, new roles. No redesign.
ROLE_CPMM = "cpmm_pool"
ROLE_DAMM = "damm_pool"
ROLE_CLMM = "clmm_pool"
ROLE_ORCA = "orca_whirlpool"


def load_univ(path: Path | None = None) -> dict:
    return json.loads((path or UNIV).read_text(encoding="utf-8"))


def accounts_for_pool(p: dict) -> list[tuple[str, str]]:
    kind = str(p.get("proto") or p.get("kind") or "")
    pk = p.get("pubkey")
    out: list[tuple[str, str]] = []
    if not pk:
        return out
    if kind == "dlmm":
        out.append((pk, ROLE_DLMM_PAIR))
        snap = p.get("snap") or {}
        lb = snap.get("lb") or {}
        active = lb.get("active_id")
        if active is None:
            return out
        for idx in d.array_indexes(int(active)):
            out.append((d.bin_array_pda(pk, idx), ROLE_DLMM_BIN))
    elif kind == "pump":
        out.append((pk, ROLE_PUMP_POOL))
        vb = p.get("vault_base") or p.get("vault_x")
        vq = p.get("vault_quote") or p.get("vault_y")
        if isinstance(vb, str) and len(vb) > 20:
            out.append((vb, ROLE_PUMP_VAULT_BASE))
        if isinstance(vq, str) and len(vq) > 20:
            out.append((vq, ROLE_PUMP_VAULT_QUOTE))
    return out


def build_submap(univ: dict | None = None) -> dict:
    univ = univ or load_univ()
    acc2: dict[str, list[dict]] = {}
    pools = []
    for p in univ.get("pools") or []:
        idx = int(p.get("idx") if p.get("idx") is not None else -1)
        kind = str(p.get("proto") or p.get("kind") or "")
        if idx < 0 or kind not in ("dlmm", "pump"):
            continue
        keys = accounts_for_pool(p)
        pools.append({"idx": idx, "kind": kind, "pubkey": p.get("pubkey"), "n_acc": len(keys)})
        for pk, role in keys:
            acc2.setdefault(pk, []).append({"pool_idx": idx, "role": role, "kind": kind})
    return {
        "accounts": acc2,
        "pools": pools,
        "n_account": len(acc2),
        "n_pool": len(pools),
    }


def diff_keys(old: dict, new: dict) -> tuple[list[str], list[str]]:
    a = set(old.get("accounts") or {})
    b = set(new.get("accounts") or {})
    return sorted(b - a), sorted(a - b)
