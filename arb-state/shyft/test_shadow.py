#!/usr/bin/env python3
"""No RPC. Hard shadow gate: association + bit-exact compare."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import shadow as sh


def _gate() -> sh.ShadowGate:
    tmp = Path(tempfile.mkdtemp(prefix="shadow-"))
    return sh.ShadowGate(cap=tmp)


class TestCompareExact(unittest.TestCase):
    def test_pump_exact(self):
        fields, bucket = sh.compare_exact(
            "pump",
            {"reserve_base": 10, "reserve_quote": 20},
            {"reserve_base": 10, "reserve_quote": 20},
            None, [],
        )
        self.assertEqual(fields, [])
        self.assertEqual(bucket, "exact")

    def test_pump_virtual_mismatch(self):
        fields, bucket = sh.compare_exact(
            "pump",
            {"reserve_base": 10, "reserve_quote": 20, "virtual_quote": 5},
            {"reserve_base": 10, "reserve_quote": 20, "virtual_quote": 0},
            {"reserve_base": 9, "reserve_quote": 19, "virtual_quote": 5},
            [],
        )
        self.assertIn("virtual_quote", fields)
        self.assertEqual(bucket, "kernel_bug")

    def test_pump_reserve_mismatch_is_kernel(self):
        fields, bucket = sh.compare_exact(
            "pump",
            {"reserve_base": 10, "reserve_quote": 20},
            {"reserve_base": 11, "reserve_quote": 20},
            {"reserve_base": 9, "reserve_quote": 19},
            [],
        )
        self.assertIn("reserves", fields)
        self.assertEqual(bucket, "kernel_bug")

    def test_pump_unpublished_write(self):
        fields, bucket = sh.compare_exact(
            "pump",
            {"reserve_base": 11, "reserve_quote": 21},
            {"reserve_base": 10, "reserve_quote": 20},
            {"reserve_base": 10, "reserve_quote": 20},
            [],
        )
        self.assertEqual(bucket, "missing_transaction_local_write")

    def test_dlmm_exact(self):
        fields, bucket = sh.compare_exact(
            "dlmm",
            {
                "active_id": 2804, "active_after": 2804,
                "vol_acc": 1, "vol_ref": 2, "idx_ref": 3,
                "touched": [{"id": 2804, "x": 9, "y": 8}],
            },
            {
                "active_id": 2804, "vol_acc": 1, "vol_ref": 2, "idx_ref": 3,
                "bins": {2804: (9, 8)},
            },
            None, [],
        )
        self.assertEqual(fields, [])
        self.assertEqual(bucket, "exact")

    def test_dlmm_bin_coverage(self):
        fields, bucket = sh.compare_exact(
            "dlmm",
            {"active_after": 2804, "touched": [{"id": 2804, "x": 1, "y": 2}]},
            {"active_id": 2804, "bins": {}},
            None, [],
        )
        self.assertIn("bin_liquidity", fields)
        self.assertEqual(bucket, "bin_traversal_account_coverage")

    def test_dlmm_vol_only(self):
        fields, bucket = sh.compare_exact(
            "dlmm",
            {"active_after": 1, "vol_acc": 99},
            {"active_id": 1, "vol_acc": 1, "bins": {}},
            None, [],
        )
        self.assertEqual(fields, ["volatility"])
        self.assertEqual(bucket, "fee_volatility_timing")


class TestAssociation(unittest.TestCase):
    def test_boot_does_not_score(self):
        g = _gate()
        g.ingest_paper({
            "kind": "opp_synced",
            "sig_hex": "aa" * 64,
            "s_prime": {"active_after": 1, "vol_acc": 1},
            "n": {"pool_idx": 26, "direction": 1, "amount_in": 1},
            "auth_slot": 100,
        })
        g.on_publish(
            idx=26, kind="dlmm", pubkey="P",
            origin="boot", stage={"sig": b"boot", "slot": 200},
            staged=[], s_before=None,
            s_pub={"active_id": 9, "vol_acc": 0, "slot": 200, "bins": {}},
        )
        self.assertEqual(g.m["shadow_total"], 0)
        self.assertEqual(g.m["shadow_exact"], 0)
        self.assertEqual(g.m["shadow_mismatch"], 0)

    def test_unassociated_txn_does_not_score(self):
        g = _gate()
        g.ingest_paper({
            "kind": "opp_synced",
            "sig_hex": "bb" * 64,
            "s_prime": {"active_after": 1},
            "n": {"pool_idx": 26},
            "auth_slot": 100,
        })
        g.on_publish(
            idx=26, kind="dlmm", pubkey="P",
            origin="tx", stage={"sig": bytes.fromhex("cc" * 64), "slot": 201},
            staged=[], s_before=None,
            s_pub={"active_id": 1, "slot": 201, "bins": {}},
        )
        self.assertEqual(g.m["shadow_total"], 0)
        self.assertEqual(len(g.pending), 1)

    def test_auth_age_is_not_a_reject(self):
        """Quiet-pool AUTH 100 slots old is still the predecessor. Score it."""
        sig = "ee" * 64
        g = _gate()
        g.ingest_paper({
            "kind": "opp_synced",
            "sig_hex": sig,
            "s_prime": {"active_after": 8, "vol_acc": 0, "tx_exact": 1},
            "n": {"pool_idx": 26},
            "auth_slot": 100,
            "tx_exact": 1,
        })
        g.on_publish(
            idx=26, kind="dlmm", pubkey="P",
            origin="tx", stage={"sig": bytes.fromhex(sig), "slot": 200},
            staged=[], s_before={"active_id": 9},
            s_pub={"active_id": 8, "vol_acc": 0, "slot": 200, "bins": {}},
        )
        self.assertEqual(g.m["shadow_total"], 1)
        self.assertEqual(g.m["shadow_exact"], 1)
        self.assertEqual(g.m["bucket"].get("stale_preceding_state", 0), 0)

    def test_ix_only_does_not_score(self):
        sig = "11" * 64
        g = _gate()
        g.ingest_paper({
            "kind": "opp_synced",
            "sig_hex": sig,
            "s_prime": {"active_after": 1, "vol_acc": 1},
            "n": {"pool_idx": 26},
            "auth_slot": 100,
            "tx_exact": 0,
            "ix_exact": 1,
        })
        g.on_publish(
            idx=26, kind="dlmm", pubkey="P",
            origin="tx", stage={"sig": bytes.fromhex(sig), "slot": 101},
            staged=[], s_before={"active_id": 1},
            s_pub={"active_id": 1, "vol_acc": 1, "slot": 101, "bins": {}},
        )
        self.assertEqual(g.m["shadow_total"], 0)
        self.assertEqual(len(g.pending), 0)

    def test_matching_sig_scores_exact(self):
        sig = "dd" * 64
        g = _gate()
        g.ingest_paper({
            "kind": "opp_synced",
            "sig_hex": sig,
            "s_prime": {"kind": "pump", "reserve_base": 5, "reserve_quote": 7},
            "n": {"pool_idx": 3, "direction": 0, "amount_in": 100},
            "auth_slot": 50,
        })
        g.on_publish(
            idx=3, kind="pump", pubkey="Q",
            origin="tx", stage={"sig": bytes.fromhex(sig), "slot": 51},
            staged=[], s_before={"reserve_base": 4, "reserve_quote": 6},
            s_pub={"reserve_base": 5, "reserve_quote": 7, "slot": 51},
        )
        self.assertEqual(g.m["shadow_total"], 1)
        self.assertEqual(g.m["shadow_exact"], 1)
        self.assertEqual(g.m["pump_exact"], 1)
        self.assertEqual(g.m["shadow_mismatch"], 0)

    def test_same_signature_keeps_independent_pool_predictions(self):
        sig = "ab" * 64
        g = _gate()
        for idx in (26, 27):
            g.ingest_paper({
                "kind": "opp_synced",
                "sig_hex": sig,
                "s_prime": {"active_after": 1},
                "n": {"pool_idx": idx},
                "auth_slot": 100,
                "tx_exact": 0,
            })
        self.assertEqual(len(g.pending), 2)
        g.on_publish(
            idx=26, kind="dlmm", pubkey="P26", origin="tx",
            stage={"sig": bytes.fromhex(sig), "slot": 101},
            staged=[], s_before=None,
            s_pub={"active_id": 1, "slot": 101, "bins": {}},
        )
        self.assertNotIn((sig, 26), g.pending)
        self.assertIn((sig, 27), g.pending)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
