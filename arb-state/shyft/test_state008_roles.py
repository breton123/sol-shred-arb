#!/usr/bin/env python3
"""No RPC. STATE-008 role / flag / seed contracts."""
from __future__ import annotations

import unittest

import submap as sm
import deps as dep


class TestState008Roles(unittest.TestCase):
    def test_roles_exist(self):
        self.assertEqual(sm.ROLE_PUMP_GLOBAL, "pump_global")
        self.assertEqual(sm.ROLE_DLMM_ORACLE, "dlmm_oracle")
        self.assertEqual(sm.ROLE_MINT, "mint")

    def test_pump_global_deterministic(self):
        a = dep.pump_global()
        b = dep.pump_global()
        self.assertEqual(a, b)
        self.assertGreater(len(a), 30)

    def test_bin_keys_are_pool_pdas(self):
        pair = "11111111111111111111111111111111"
        keys = dep.bin_keys_for_active(pair, 0)
        self.assertGreaterEqual(len(keys), 1)
        self.assertEqual(len(set(keys)), len(keys))

    def test_incomplete_pump_without_vaults(self):
        derv = dep.derive_pool({"idx": 1, "proto": "pump", "pubkey": "x" * 32})
        roles = [r for _, r in derv["required"]]
        self.assertIn(sm.ROLE_PUMP_POOL, roles)
        self.assertIn(sm.ROLE_PUMP_GLOBAL, roles)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
