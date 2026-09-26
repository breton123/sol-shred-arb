"""STATE-010 — signature-keyed publication barrier.

sig X
  expected = {pair, binA, …}
  received ⊂ expected  → HOLD
  received == expected → eligible; verify account versions before publication
  next slot + incomplete → STATE_TX_INCOMPLETE, do not AUTH
"""
from __future__ import annotations


def write_identity(row: dict) -> tuple:
    """Provider-scoped identity and immutable account contents; not chain order."""
    return (row.get("provider_generation"), row.get("bank_id"), row.get("slot"),
            row.get("write_version"), bytes(row.get("txn_sig") or b""),
            row.get("owner"), row.get("lamports"), bytes(row.get("data") or b""))

class TxBarrier:
    def __init__(self) -> None:
        # sig → {idx: {expected, received, slot, kind, pubkey, variant}}
        self.by_sig: dict[str, dict[int, dict]] = {}
        self.m = {
            "tx_shape": 0,
            "publish_wait_pair": 0,
            "publish_wait_bin": 0,
            "publish_wait_vault": 0,
            "publish_wait_shape": 0,
            "publish_incomplete_at_boundary": 0,
            "evicted_transactions": 0,
        }

    def note_tx(self, sig: str, slot: int, expect_by_idx: dict[int, dict]) -> None:
        if not sig or not expect_by_idx:
            return
        row = self.by_sig.setdefault(sig, {})
        for idx, spec in expect_by_idx.items():
            cur = row.setdefault(int(idx), {
                "expected": set(),
                "received": set(),
                "slot": int(slot),
                "kind": spec.get("kind"),
                "pubkey": spec.get("pubkey"),
                "variant": spec.get("variant"),
            })
            cur["expected"] |= set(spec.get("expected") or [])
            cur["slot"] = int(slot)
        self.m["tx_shape"] += 1
        while len(self.by_sig) > 4096:
            oldest = next(iter(self.by_sig))
            self.by_sig.pop(oldest, None)
            self.m["evicted_transactions"] += 1

    def note_write(self, sig: str, slot: int, pool_idx: int, pk: str,
                   version: dict | None = None) -> None:
        if not sig or not pk:
            return
        row = self.by_sig.setdefault(sig, {})
        cur = row.setdefault(int(pool_idx), {
            "expected": set(),
            "received": set(),
            "slot": int(slot),
            "kind": None,
            "pubkey": None,
            "variant": None,
        })
        cur["received"].add(pk)
        if version is not None:
            versions = cur.setdefault("versions", {})
            identity = write_identity(version)
            if pk in versions and versions[pk] != identity:
                cur["version_conflict"] = True
            versions[pk] = identity
        if not cur.get("slot"):
            cur["slot"] = int(slot)
        while len(self.by_sig) > 4096:
            self.by_sig.pop(next(iter(self.by_sig)))
            self.m["evicted_transactions"] += 1

    def spec(self, sig: str, pool_idx: int) -> dict | None:
        return (self.by_sig.get(sig) or {}).get(int(pool_idx))

    def has_shape(self, sig: str, pool_idx: int) -> bool:
        sp = self.spec(sig, pool_idx)
        return bool(sp and sp.get("expected"))

    def missing(self, sig: str, pool_idx: int) -> set[str]:
        sp = self.spec(sig, pool_idx)
        if not sp or not sp.get("expected"):
            return set()
        return set(sp["expected"]) - set(sp["received"])

    def can_commit(self, sig: str, pool_idx: int) -> bool:
        sp = self.spec(sig, pool_idx)
        if not sp or not sp.get("expected"):
            return False
        return set(sp["expected"]) <= set(sp["received"])

    def snapshot(self, sig: str, pool_idx: int, required: set[str], latest: dict) -> tuple[str, dict | None]:
        """Freeze one quote read set and reject superseded transaction writes.

        Untouched dependencies still need a predecessor/ancestry certificate.
        This guard alone must never be advertised as full state coherence.
        """
        sp = self.spec(sig, pool_idx)
        if not self.can_commit(sig, pool_idx):
            return "writes_incomplete", None
        if sp.get("version_conflict"):
            return "write_version_conflict", None
        if not set(sp["expected"]) <= required:
            return "read_set_incomplete", None
        rows = {pk: dict(latest.get(pk) or {}) for pk in required}
        if any(not row.get("data") for row in rows.values()):
            return "account_missing", None
        if any(int(row.get("slot") or 0) > sp["slot"] for row in rows.values()):
            return "dependency_from_future_slot", None
        for row in rows.values():
            row["data"] = bytes(row["data"])
        for pk in sp["expected"]:
            captured = sp.get("versions", {}).get(pk)
            if captured is None:
                return "write_identity_missing", None
            if captured != write_identity(rows[pk]):
                return "write_superseded", None
            if rows[pk].get("slot") != sp["slot"] or bytes(rows[pk].get("txn_sig") or b"").hex() != sig:
                return "write_identity_mismatch", None
        return "available", rows

    def mark_wait(self, missing: set[str], role_of) -> None:
        if not missing:
            return
        saw = set()
        for pk in missing:
            role = role_of(pk) if callable(role_of) else None
            if role == "dlmm_lbpair" or role == "pump_pool":
                saw.add("pair")
            elif role == "dlmm_binarray":
                saw.add("bin")
            elif role in ("pump_vault_base", "pump_vault_quote"):
                saw.add("vault")
            else:
                saw.add("bin")
        if "pair" in saw:
            self.m["publish_wait_pair"] += 1
        if "bin" in saw:
            self.m["publish_wait_bin"] += 1
        if "vault" in saw:
            self.m["publish_wait_vault"] += 1

    def expire_at_boundary(self, stream_slot: int) -> list[tuple[str, int]]:
        """Incomplete expected sets once the next slot has started."""
        dead = []
        for sig, pools in list(self.by_sig.items()):
            for idx, sp in list(pools.items()):
                if not sp.get("expected"):
                    continue
                if int(stream_slot) <= int(sp.get("slot") or 0):
                    continue
                if set(sp["expected"]) <= set(sp["received"]):
                    continue
                dead.append((sig, int(idx)))
        return dead

    def drop(self, sig: str, pool_idx: int | None = None) -> None:
        if pool_idx is None:
            self.by_sig.pop(sig, None)
            return
        row = self.by_sig.get(sig)
        if not row:
            return
        row.pop(int(pool_idx), None)
        if not row:
            self.by_sig.pop(sig, None)
