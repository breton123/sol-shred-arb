"""Hard STATE-008 shadow gate. Predicted S' vs next associated coherent S.

Never counts an unassociated publish as exact. Mismatches are classified
and bundled; they are not averaged or silently resynced into success.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import os
CAP = Path(os.environ.get("STATE008_CAP") or "/home/louis/captures/state008")
MISDIR = CAP / "mismatch"
SHADOW = CAP / "SHADOW.jsonl"
EXPLAIN = CAP / "FIRST_MISMATCH.json"

BUCKETS = (
    "kernel_bug",
    "missing_transaction_local_write",
    "wrong_transaction_association",
    "stale_preceding_state",
    "fee_volatility_timing",
    "bin_traversal_account_coverage",
    "fork_order",
    "trigger_decode_error",
    "state_missing",
    "publication_incomplete",
)

FIELD_KEYS = (
    "active_id", "volatility", "bin_liquidity", "reserves", "virtual_quote",
    "fee_state", "ordering",
)


def sig_hex(raw) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("0x"):
            s = s[2:]
        return s.lower() or None
    if isinstance(raw, (bytes, bytearray)):
        if raw == b"boot" or not raw:
            return None
        return bytes(raw).hex()
    return None


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


class ShadowGate:
    def __init__(self, cap: Path | None = None) -> None:
        self.cap = cap or CAP
        self.misdir = self.cap / "mismatch"
        self.shadow_path = self.cap / "SHADOW.jsonl"
        self.explain_path = self.cap / "FIRST_MISMATCH.json"
        self.pending: dict[tuple[str, int], dict] = {}  # (sig_hex, pool_idx) -> paper rec
        self.by_idx: dict[int, list[tuple[str, int]]] = {}
        self.m = {
            "paper_ingested": 0,
            "shadow_total": 0,
            "shadow_exact": 0,
            "shadow_mismatch": 0,
            "shadow_state_missing": 0,
            "shadow_trigger_decode_error": 0,
            "shadow_wrong_association": 0,
            "pump_total": 0,
            "pump_exact": 0,
            "dlmm_total": 0,
            "dlmm_exact": 0,
            "tx_exact_total": 0,
            "tx_exact_shadowed": 0,
            "tx_exact_bitexact": 0,
            "tx_exact_mismatch": 0,
            "fastsoak_ingested": 0,
            "publication_mismatch": 0,
            "prediction_mismatch": 0,
            "prediction_bug": 0,
            "publication_bug": 0,
            "unsupported_shape": 0,
            "known_kernel_limitation": 0,
            "mismatch": {k: 0 for k in FIELD_KEYS},
            "bucket": {k: 0 for k in BUCKETS},
        }
        self.misdir.mkdir(parents=True, exist_ok=True)

    def ingest_direct(self, rec: dict) -> None:
        """TX_EXACT ∩ preceding AUTH. No OrbitFlare / opp_synced required."""
        row = dict(rec)
        row["kind"] = "opp_synced"
        row["tx_exact"] = 1
        row["source"] = row.get("source") or "fastsoak"
        self.m["fastsoak_ingested"] += 1
        self.ingest_paper(row)

    def ingest_paper(self, rec: dict) -> None:
        if rec.get("kind") != "opp_synced":
            return
        self.m["paper_ingested"] += 1
        sp = rec.get("s_prime")
        n = rec.get("n") or {}
        idx = n.get("pool_idx")
        sig = sig_hex(rec.get("sig_hex"))
        if idx is None:
            return
        if sp is None:
            self.m["shadow_trigger_decode_error"] += 1
            return
        if not sig:
            self.m["shadow_trigger_decode_error"] += 1
            return
        age = rec.get("auth_age_slots")
        if age is None:
            age = (rec.get("fresh") or {}).get("age_slots")
        key = (sig, int(idx))
        self.pending[key] = {
            "sig": sig,
            "idx": int(idx),
            "s_prime": sp,
            "n": n,
            "auth_slot": rec.get("auth_slot"),
            "auth_generation": rec.get("auth_generation"),
            "auth_age_slots": age,
            "tx_exact": rec.get("tx_exact"),
            "ix_exact": rec.get("ix_exact"),
            "state_version_before": rec.get("state_version_before"),
            "pool": rec.get("pool"),
            "raw": rec,
            "t_ingest": time.time(),
        }
        if rec.get("tx_exact") == 1:
            self.m["tx_exact_total"] += 1
        self.by_idx.setdefault(int(idx), []).append(key)
        if len(self.pending) > 512:
            oldest = next(iter(self.pending))
            stale = self.pending.get(oldest)
            if stale:
                self._emit(
                    bucket="state_missing",
                    reason="pending_overflow",
                    pend=stale, kind="unknown", pubkey=stale.get("pool") or "",
                    origin="expire", stage={}, staged=[],
                    s_before=None, s_pub={}, fields=[],
                )
            self._drop(oldest)

    def _drop(self, key: tuple[str, int]) -> None:
        rec = self.pending.pop(key, None)
        if not rec:
            return
        lst = self.by_idx.get(rec["idx"]) or []
        self.by_idx[rec["idx"]] = [item for item in lst if item != key]

    def on_publish(
        self,
        *,
        idx: int,
        kind: str,
        pubkey: str,
        origin: str,
        stage: dict,
        staged: list,
        s_before: dict | None,
        s_pub: dict,
    ) -> None:
        """Only a txn-associated paper prediction may score exact."""
        txn = sig_hex(stage.get("sig"))
        if origin == "boot" or stage.get("sig") == b"boot" or not txn:
            return
        pend_key = (txn, int(idx))
        pend = self.pending.get(pend_key)
        if pend is None:
            # YS write we did not predict. Not a sample. Not exact.
            return
        tx_exact = pend.get("tx_exact")
        if tx_exact is None:
            tx_exact = (pend.get("raw") or {}).get("tx_exact")
        if tx_exact == 0:
            self._drop(pend_key)
            return
        auth = pend.get("auth_slot")
        pub_slot = s_pub.get("slot")
        if auth is not None and pub_slot is not None and int(pub_slot) + 64 < int(auth):
            self._emit(
                bucket="fork_order",
                reason="publish_slot_before_paper_auth",
                pend=pend, kind=kind, pubkey=pubkey, origin=origin,
                stage=stage, staged=staged, s_before=s_before, s_pub=s_pub,
                fields=["ordering"],
            )
            self._drop(pend_key)
            return
        if stage.get("wait_slot") and not txn:
            self._emit(
                bucket="fork_order",
                reason="multi_tx_same_slot",
                pend=pend, kind=kind, pubkey=pubkey, origin=origin,
                stage=stage, staged=staged, s_before=s_before, s_pub=s_pub,
                fields=["ordering"],
            )
            self._drop(pend_key)
            return

        fields, bucket = compare_exact(kind, pend["s_prime"], s_pub, s_before, staged)
        self.m["shadow_total"] += 1
        if pend.get("tx_exact") == 1:
            self.m["tx_exact_shadowed"] += 1
        if kind == "pump":
            self.m["pump_total"] += 1
        else:
            self.m["dlmm_total"] += 1
        if not fields:
            self.m["shadow_exact"] += 1
            if pend.get("tx_exact") == 1:
                self.m["tx_exact_bitexact"] += 1
            if kind == "pump":
                self.m["pump_exact"] += 1
            else:
                self.m["dlmm_exact"] += 1
            self._log({
                "ts": _utc(), "idx": idx, "kind": kind, "class": "exact",
                "bucket": "exact", "sig": txn, "slot": pub_slot, "fields": [],
            })
        else:
            for f in fields:
                if f in self.m["mismatch"]:
                    self.m["mismatch"][f] += 1
                elif f.startswith("bin"):
                    self.m["mismatch"]["bin_liquidity"] += 1
            if pend.get("tx_exact") == 1:
                self.m["tx_exact_mismatch"] += 1
            plane = "publication" if bucket in (
                "missing_transaction_local_write",
                "bin_traversal_account_coverage",
                "publication_incomplete",
            ) else "prediction"
            if plane == "publication":
                self.m["publication_mismatch"] += 1
                self.m["publication_bug"] += 1
            else:
                self.m["prediction_mismatch"] += 1
                self.m["prediction_bug"] += 1
            self._emit(
                bucket=bucket,
                reason="bit_exact_fail",
                pend=pend, kind=kind, pubkey=pubkey, origin=origin,
                stage=stage, staged=staged, s_before=s_before, s_pub=s_pub,
                fields=fields,
            )
        self._drop(pend_key)

    def _emit(self, bucket: str, reason: str, pend: dict, kind: str, pubkey: str,
              origin: str, stage: dict, staged: list, s_before, s_pub, fields: list) -> None:
        if bucket == "wrong_transaction_association":
            self.m["shadow_wrong_association"] += 1
        elif bucket == "state_missing":
            self.m["shadow_state_missing"] += 1
        elif bucket == "stale_preceding_state":
            pass
        elif bucket == "trigger_decode_error":
            self.m["shadow_trigger_decode_error"] += 1
        else:
            self.m["shadow_mismatch"] += 1
        self.m["bucket"][bucket] = self.m["bucket"].get(bucket, 0) + 1
        n = pend.get("n") or {}
        bundle = {
            "ts": _utc(),
            "bucket": bucket,
            "reason": reason,
            "fields": fields,
            "trigger_sig": pend.get("sig"),
            "slot": s_pub.get("slot") if s_pub else stage.get("slot"),
            "pool": pubkey,
            "idx": pend.get("idx"),
            "kind": kind,
            "direction": n.get("direction"),
            "amount_in": n.get("amount_in"),
            "auth_slot": pend.get("auth_slot"),
            "state_version_before": pend.get("state_version_before"),
            "s_before": s_before,
            "s_prime": pend.get("s_prime"),
            "published_s": s_pub,
            "plane": "publication" if bucket in (
                "missing_transaction_local_write",
                "bin_traversal_account_coverage",
                "publication_incomplete",
            ) else "prediction",
            "staged_writes": staged,
            "stage": {
                "slot": stage.get("slot"),
                "wait_slot": stage.get("wait_slot"),
                "sig": sig_hex(stage.get("sig")),
                "origin": origin,
            },
            "n_ix": (pend.get("raw") or {}).get("n_ix"),
            "shred": (pend.get("raw") or {}).get("shred"),
            "frame": (pend.get("raw") or {}).get("frame"),
            "touched_bin_arrays": [
                w for w in staged
                if (w.get("role") in ("dlmm_binarray", "dlmm_bin"))
            ],
            "update_order": [w.get("pubkey") for w in staged],
        }
        path = self.misdir / f"{pend.get('sig') or 'unknown'}_{pend.get('idx')}.json"
        path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
        if bucket not in ("state_missing",) and not self.explain_path.exists():
            self.explain_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
        self._log({
            "ts": bundle["ts"], "idx": bundle["idx"], "kind": kind,
            "class": "mismatch", "bucket": bucket, "reason": reason,
            "sig": pend.get("sig"), "slot": bundle["slot"], "fields": fields,
            "bundle": str(path),
        })
        print(
            f"STATE-008  SHADOW {bucket} idx={bundle['idx']} "
            f"fields={fields} reason={reason}",
            flush=True,
        )

    def _log(self, rec: dict) -> None:
        with self.shadow_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def rates(self) -> dict:
        def pct(num, den):
            return (100.0 * num / den) if den else None
        return {
            **self.m,
            "pump_exact_pct": pct(self.m["pump_exact"], self.m["pump_total"]),
            "dlmm_exact_pct": pct(self.m["dlmm_exact"], self.m["dlmm_total"]),
            "tx_exact_total": self.m["tx_exact_total"],
            "tx_exact_shadowed": self.m["tx_exact_shadowed"],
            "tx_exact_bitexact": self.m["tx_exact_bitexact"],
            "tx_exact_mismatch": self.m["tx_exact_mismatch"],
            "publication_mismatch": self.m["publication_mismatch"],
            "prediction_mismatch": self.m["prediction_mismatch"],
        }

    def expire_stale(self, max_age_s: float = 32.0) -> None:
        """Unmatched paper predictions are state_missing, not silent success."""
        now = time.time()
        for key, pend in list(self.pending.items()):
            if now - float(pend.get("t_ingest") or 0) < max_age_s:
                continue
            self._emit(
                bucket="state_missing",
                reason="no_associated_publish",
                pend=pend, kind="unknown", pubkey=pend.get("pool") or "",
                origin="expire", stage={}, staged=[],
                s_before=None, s_pub={}, fields=[],
            )
            self._drop(key)


def compare_exact(kind: str, s_prime: dict, s_pub: dict, s_before, staged: list) -> tuple[list[str], str]:
    fields: list[str] = []
    if kind == "pump":
        def _amt(row, *keys):
            if not isinstance(row, dict):
                return None
            for k in keys:
                if row.get(k) is not None:
                    return int(row[k])
            return None
        prb = _amt(s_prime, "base_vault_amount", "reserve_base")
        prq = _amt(s_prime, "quote_vault_amount", "reserve_quote")
        urb = _amt(s_pub, "base_vault_amount", "reserve_base")
        urq = _amt(s_pub, "quote_vault_amount", "reserve_quote")
        pv = _amt(s_prime, "virtual_quote_reserves", "virtual_quote")
        uv = _amt(s_pub, "virtual_quote_reserves", "virtual_quote")
        if prb is not None and urb is not None and prb != urb:
            fields.append("reserves")
        if prq is not None and urq is not None and prq != urq:
            fields.append("reserves")
        if pv is not None and uv is not None and pv != uv:
            fields.append("virtual_quote")
        if not fields:
            return [], "exact"
        if s_before and (
            _amt(s_before, "base_vault_amount", "reserve_base") == urb
            and _amt(s_before, "quote_vault_amount", "reserve_quote") == urq
        ):
            return fields, "missing_transaction_local_write"
        return fields, "kernel_bug"

    # DLMM: active_id, volatility, every touched bin, fee state. Not close enough.
    if s_prime.get("active_after") is not None:
        want_active = int(s_prime["active_after"])
    elif s_prime.get("active_id") is not None:
        want_active = int(s_prime["active_id"])
    else:
        want_active = None
    if want_active is not None and want_active != int(s_pub.get("active_id") or -10**9):
        fields.append("active_id")
    if s_prime.get("vol_acc") is not None and int(s_prime["vol_acc"]) != int(s_pub["vol_acc"] if s_pub.get("vol_acc") is not None else -1):
        fields.append("volatility")
    if s_prime.get("vol_ref") is not None and int(s_prime["vol_ref"]) != int(s_pub["vol_ref"] if s_pub.get("vol_ref") is not None else -1):
        fields.append("volatility")
    if s_prime.get("idx_ref") is not None and int(s_prime["idx_ref"]) != int(s_pub.get("idx_ref") or -10**9):
        fields.append("fee_state")
    if s_prime.get("last_upd") is not None and s_pub.get("last_upd") is not None:
        if int(s_prime["last_upd"]) != int(s_pub["last_upd"]):
            fields.append("fee_state")
    bins = s_pub.get("bins") or {}
    missing_bin = False
    for b in s_prime.get("touched") or []:
        bid = int(b["id"])
        xy = bins.get(bid)
        if xy is None:
            xy = bins.get(str(bid))
        if xy is None:
            missing_bin = True
            fields.append("bin_liquidity")
        elif tuple(xy) != (int(b["x"]), int(b["y"])):
            fields.append("bin_liquidity")
    if not fields:
        return [], "exact"
    if missing_bin:
        return list(dict.fromkeys(fields)), "bin_traversal_account_coverage"
    only_vol = set(fields) <= {"volatility", "fee_state"}
    if only_vol:
        return fields, "fee_volatility_timing"
    if s_before and s_before.get("active_id") == s_pub.get("active_id"):
        if "active_id" in fields or "bin_liquidity" in fields:
            return list(dict.fromkeys(fields)), "missing_transaction_local_write"
    return list(dict.fromkeys(fields)), "kernel_bug"
