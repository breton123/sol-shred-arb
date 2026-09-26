"""STATE-010 — derive the pricing write set of one exact swap.

Expected writes are the intersection of the instruction's accounts with
the quote-kernel state for that pool. Other ix accounts (user ATAs,
reserves, token programs) are not kernel state and are not waited on.
"""
from __future__ import annotations

import submap as sm

DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

DLMM_SWAP2 = bytes.fromhex("414b3f4ceb5b5b88")
DLMM_SWAP1 = bytes.fromhex("f8c69e91e17587c8")
PUMP_SELL = bytes.fromhex("33e685a4017f83ad")
PUMP_BUY_EQ = bytes.fromhex("c62e1552b4d9e870")
PUMP_BUY = bytes.fromhex("66063d1201daebea")  # exact-out: base_amount_out

EXACT = {
    (DLMM, DLMM_SWAP2): "dlmm_swap2",
    (DLMM, DLMM_SWAP1): "dlmm_swap1",
    (PUMP, PUMP_SELL): "pump_sell",
    (PUMP, PUMP_BUY_EQ): "pump_buy_exact_quote",
    (PUMP, PUMP_BUY): "pump_buy_exact_out",
}

DLMM_PRICING = {sm.ROLE_DLMM_PAIR, sm.ROLE_DLMM_BIN}
PUMP_PRICING = {
    sm.ROLE_PUMP_POOL, sm.ROLE_PUMP_VAULT_BASE, sm.ROLE_PUMP_VAULT_QUOTE,
}
# Remaining accounts on a 15-account Meteora swap are bin arrays.
DLMM_FIXED = 15


def tx_exact_status(instructions: list[dict]) -> dict:
    """TX_EXACT iff every DLMM/Pump ix is a supported exact variant.

    Direct = at least one exact leg. Unknown dex discs fail closed.
    """
    exact = 0
    unknown = 0
    variants: list[str] = []
    for ix in instructions:
        prog = ix.get("program") or ""
        if prog not in (DLMM, PUMP):
            continue
        data = ix.get("data") or b""
        if isinstance(data, str):
            unknown += 1
            continue
        v = classify_ix(prog, data)
        if v is None:
            unknown += 1
        else:
            exact += 1
            variants.append(v)
    return {
        "tx_exact": exact > 0 and unknown == 0,
        "n_exact": exact,
        "n_unknown": unknown,
        "variants": variants,
    }


def classify_ix(program: str, data: bytes) -> str | None:
    if not data or len(data) < 8:
        return None
    return EXACT.get((program, data[:8]))


def _role_of(pk: str, idx: int, acc_deps: dict) -> str | None:
    for row in acc_deps.get(pk) or []:
        if int(row.get("pool_idx")) == int(idx):
            return row.get("role")
    return None


def expected_for_ix(
    kind: str,
    accounts: list[str],
    pool_idx: int,
    acc_deps: dict,
) -> set[str]:
    """Kernel-state accounts this exact swap can write."""
    if not accounts:
        return set()
    pricing = DLMM_PRICING if kind == "dlmm" else PUMP_PRICING
    out = set()
    out.add(accounts[0])
    for i, pk in enumerate(accounts):
        role = _role_of(pk, pool_idx, acc_deps)
        if role in pricing:
            out.add(pk)
        elif kind == "dlmm" and i >= DLMM_FIXED and pk not in (DLMM, PUMP):
            # Remaining accounts are bin arrays, including newly traversed ones.
            out.add(pk)
    return out


def expect_from_instructions(
    keys: list[str],
    instructions: list[dict],
    acc_deps: dict,
    pools_by_pk: dict[str, int],
) -> dict[int, dict]:
    """pool_idx → {expected, kind, pubkey, variant}."""
    by_idx: dict[int, dict] = {}
    for ix in instructions:
        prog = ix.get("program") or ""
        data = ix.get("data") or b""
        if isinstance(data, str):
            continue
        variant = classify_ix(prog, data)
        if variant is None:
            continue
        accs = list(ix.get("accounts") or [])
        if not accs:
            continue
        pool = accs[0]
        idx = pools_by_pk.get(pool)
        if idx is None:
            continue
        kind = "dlmm" if variant.startswith("dlmm") else "pump"
        exp = expected_for_ix(kind, accs, idx, acc_deps)
        row = by_idx.setdefault(int(idx), {
            "expected": set(), "kind": kind, "pubkey": pool, "variant": variant,
        })
        row["expected"] |= exp
        row["variant"] = variant
    return by_idx


def _b58(raw: bytes, _pk) -> str:
    return _pk(raw) if raw else ""


def _ix_accounts(ix, keys: list[str]) -> list[str]:
    raw = getattr(ix, "accounts", None)
    out = []
    if raw is None:
        return out
    if isinstance(raw, (bytes, bytearray)):
        idxs = list(raw)
    else:
        idxs = list(raw)
    for i in idxs:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(keys):
            out.append(keys[i])
    return out


def parse_geyser_tx(info, _pk) -> dict | None:
    """Normalize a Yellowstone SubscribeUpdateTransactionInfo."""
    try:
        tx = info.transaction
        msg = tx.message
        sig = bytes(info.signature)
        if not sig:
            return None
        keys = [_b58(bytes(k), _pk) for k in list(msg.account_keys)]
        meta = getattr(info, "meta", None)
        if meta is not None:
            for attr in ("loaded_writable_addresses", "loaded_readonly_addresses"):
                for k in list(getattr(meta, attr, []) or []):
                    keys.append(_b58(bytes(k), _pk))
        inners_by: dict[int, list] = {}
        if meta is not None:
            for group in list(getattr(meta, "inner_instructions", []) or []):
                gi = int(getattr(group, "index", 0) or 0)
                inners_by.setdefault(gi, []).extend(list(getattr(group, "instructions", []) or []))
        ixs = []
        for i, ix in enumerate(list(msg.instructions)):
            pidx = int(ix.program_id_index)
            if pidx < len(keys):
                ixs.append({
                    "program": keys[pidx],
                    "accounts": _ix_accounts(ix, keys),
                    "data": bytes(ix.data),
                    "outer_ix": i,
                    "inner_ordinal": None,
                })
            for j, iix in enumerate(inners_by.get(i) or []):
                pidx = int(getattr(iix, "program_id_index", 0))
                if pidx >= len(keys):
                    continue
                ixs.append({
                    "program": keys[pidx],
                    "accounts": _ix_accounts(iix, keys),
                    "data": bytes(getattr(iix, "data", b"") or b""),
                    "outer_ix": i,
                    "inner_ordinal": j,
                })
        return {"sig": sig.hex(), "keys": keys, "instructions": ixs}
    except Exception:
        return None
