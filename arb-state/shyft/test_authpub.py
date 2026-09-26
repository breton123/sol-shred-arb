#!/usr/bin/env python3
"""No RPC. AUTH-PUBLISH layout + predecessor pick."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import authpub as a


class TestLayout(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(a.ENT, 2176)
        self.assertEqual(a._ENT_HDR.size, 128)
        self.assertEqual(a.POOL, a.POOL_HDR + a.RING * a.ENT)
        self.assertEqual(a.map_size(2), a.HDR + 2 * a.POOL)

    def test_roundtrip_and_pred(self):
        tmp = Path(tempfile.mkdtemp()) / "auth.shm"
        pub = a.AuthPub(tmp, pool_cap=8)
        pub.create()
        sig_n = b"N" * 64
        sig_a = b"A" * 64
        pub.publish(3, slot=100, blob=b"s0", proto=1, sig=sig_a, txn_index=1)
        pub.publish(3, slot=101, blob=b"s1", proto=1, sig=sig_n, txn_index=2)
        ring = pub.dump_ring(3)
        self.assertEqual(len(ring), 2)
        self.assertEqual(ring[0]["slot"], 101)
        self.assertEqual(ring[0]["txn_index"], 2)
        pred = a.choose_pred(ring, 101, sig_n)
        self.assertIsNotNone(pred)
        self.assertEqual(pred["slot"], 100)
        pred2 = a.choose_pred(ring, 102, None)
        self.assertEqual(pred2["slot"], 101)
        same_slot = a.choose_pred(ring, 101, b"Z" * 64)
        self.assertIsNone(same_slot)
        pub.close()

    def test_account_write_version_is_not_transaction_index(self):
        tmp = Path(tempfile.mkdtemp()) / "auth.shm"
        pub = a.AuthPub(tmp, pool_cap=8)
        pub.create()
        pub.publish(3, slot=100, blob=b"s0", proto=1, sig=b"A" * 64,
                    max_account_write_version=17_600_000_000)
        entry = pub.dump_ring(3)[0]
        self.assertEqual(entry["txn_index"], a.TXN_INDEX_UNKNOWN)
        self.assertEqual(entry["max_account_write_version"], 17_600_000_000)
        self.assertFalse(entry["flags"] & a.HAS_TXN_INDEX)
        self.assertTrue(entry["flags"] & a.HAS_ACCOUNT_WRITE_VERSION)
        pub.close()

    def test_gap_is_not_skipped_for_older_state(self):
        sig_n = b"N" * 64
        entries = [
            {"slot": 105, "sig": sig_n, "flags": a.COHERENT, "coherent": 1},
            {"slot": 104, "sig": b"G" * 64,
             "flags": a.COHERENT | a.GAPPED, "coherent": 1},
            {"slot": 100, "sig": b"A" * 64, "flags": a.COHERENT, "coherent": 1},
        ]
        self.assertIsNone(a.choose_pred(entries, 105, sig_n))

    def test_latest_strictly_prior_entry_wins(self):
        entries = [
            {"slot": 105, "sig": b"B" * 64, "flags": a.COHERENT, "coherent": 1},
            {"slot": 100, "sig": b"A" * 64, "flags": a.COHERENT, "coherent": 1},
        ]
        self.assertEqual(a.choose_pred(entries, 106, None)["slot"], 105)

    def test_writer_generation_survives_reopen(self):
        tmp = Path(tempfile.mkdtemp()) / "auth.shm"
        first = a.AuthPub(tmp, pool_cap=8)
        first.create()
        first.publish(3, slot=100, blob=b"s0", proto=1, sig=b"A" * 64)
        first.close()
        second = a.AuthPub(tmp, pool_cap=8)
        second.open()
        second.publish(3, slot=101, blob=b"s1", proto=1, sig=b"B" * 64)
        self.assertEqual(second.dump_ring(3)[0]["generation"], 2)
        second.close()

    def test_reconnect_hides_prior_history_and_preserves_version_monotonicity(self):
        with tempfile.TemporaryDirectory() as folder:
            pub = a.AuthPub(Path(folder)/"auth", pool_cap=2)
            pub.create()
            pub.publish(1, slot=100, blob=b"old", proto=1, sig=b"A"*64)
            old_version = pub.dump_ring(1)[0]["generation"]
            pub.set_ready(True)
            pub.reset_history()
            self.assertEqual(pub.dump_ring(1), [])
            pub.publish(1, slot=101, blob=b"new", proto=1, sig=b"B"*64)
            rows = pub.dump_ring(1)
            self.assertEqual(len(rows), 1)
            self.assertGreater(rows[0]["generation"], old_version)
            self.assertIsNone(a.choose_pred(rows, 101, b"B"*64))
            pub.close()


if __name__ == "__main__":
    raise SystemExit(unittest.main())
