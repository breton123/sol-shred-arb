#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import shadow as sh
import txexpect as txe


class TestTxExact(unittest.TestCase):
    def test_one_swap2_is_exact(self):
        st = txe.tx_exact_status([{
            "program": txe.DLMM,
            "data": txe.DLMM_SWAP2 + bytes(16),
        }])
        self.assertTrue(st["tx_exact"])
        self.assertEqual(st["n_exact"], 1)
        self.assertEqual(st["n_unknown"], 0)

    def test_unknown_disc_fails_closed(self):
        st = txe.tx_exact_status([{
            "program": txe.DLMM,
            "data": bytes(8) + bytes(16),
        }])
        self.assertFalse(st["tx_exact"])
        self.assertEqual(st["n_unknown"], 1)

    def test_pump_sell_and_unknown_not_exact(self):
        st = txe.tx_exact_status([
            {"program": txe.PUMP, "data": txe.PUMP_SELL + bytes(16)},
            {"program": txe.PUMP, "data": bytes(8) + bytes(16)},
        ])
        self.assertFalse(st["tx_exact"])
        self.assertEqual(st["n_exact"], 1)
        self.assertEqual(st["n_unknown"], 1)

    def test_pump_buy_exact_out_is_exact(self):
        st = txe.tx_exact_status([
            {"program": txe.PUMP, "data": txe.PUMP_SELL + bytes(16)},
            {"program": txe.PUMP, "data": txe.PUMP_BUY + bytes(16)},
        ])
        self.assertTrue(st["tx_exact"])
        self.assertEqual(st["n_exact"], 2)


class TestIngestDirect(unittest.TestCase):
    def test_bypasses_orbitflare_kind(self):
        g = sh.ShadowGate(cap=Path(tempfile.mkdtemp(prefix="fs-")))
        g.ingest_direct({
            "sig_hex": "aa" * 32,
            "pool": "P",
            "n": {"pool_idx": 3},
            "s_prime": {"active_after": 1, "touched": []},
            "auth_slot": 10,
        })
        self.assertEqual(g.m["fastsoak_ingested"], 1)
        self.assertEqual(g.m["tx_exact_total"], 1)
        self.assertIn(("aa" * 32, 3), g.pending)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
