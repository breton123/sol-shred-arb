#!/usr/bin/env python3
import unittest

from reduce_soak import dlmm_class, pump_class, reduce


class ReduceSoak(unittest.TestCase):
    def test_pump_virtual_config(self):
        b = {
            "kind": "pump",
            "bucket": "kernel_bug",
            "fields": ["reserves"],
            "s_before": {"reserve_base": 100, "reserve_quote": 200, "virtual_quote": 0},
            "s_prime": {"reserve_base": 90, "reserve_quote": 210, "virtual_quote": 0},
            "published_s": {"reserve_base": 88, "reserve_quote": 212},
            "staged_writes": [{"role": "pump_vault_base"}],
        }
        self.assertEqual(pump_class(b), "virtual_reserve_config")

    def test_pump_assoc(self):
        self.assertEqual(
            pump_class({"kind": "pump", "bucket": "wrong_transaction_association", "fields": []}),
            "wrong_tx_association",
        )

    def test_dlmm_missing_bin(self):
        b = {
            "kind": "dlmm",
            "bucket": "bin_traversal_account_coverage",
            "fields": ["bin_liquidity"],
            "s_prime": {"touched": [{"id": 1, "x": 1, "y": 2}]},
            "published_s": {"bins": {}},
        }
        self.assertEqual(dlmm_class(b), "missing_bin")

    def test_dlmm_orders_heuristic(self):
        b = {
            "kind": "dlmm",
            "bucket": "kernel_bug",
            "fields": ["bin_liquidity"],
            "s_prime": {"active_id": 10, "touched": [{"id": 10, "x": 1, "y": 2}]},
            "published_s": {"active_id": 10, "bins": {"10": [1, 9]}},
        }
        self.assertEqual(dlmm_class(b), "order_inventory_related")

    def test_reduce_empty(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "SHADOW.jsonl").write_text(
                '{"class":"exact","kind":"pump"}\n{"class":"mismatch","kind":"pump"}\n',
                encoding="utf-8",
            )
            doc = reduce(p)
            self.assertEqual(doc["shadow"]["exact"]["pump"], 1)
            self.assertEqual(doc["pump"]["n"], 0)


if __name__ == "__main__":
    unittest.main()
