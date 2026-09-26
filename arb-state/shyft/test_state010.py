#!/usr/bin/env python3
"""STATE-010: pair-then-bin and reverse must not AUTH mid-transaction.

Replay of 2sjGjP4KjtwZA8cQXTHJvPbFbhSmW76H1e8CZEoLAwE2TvZqK4QC4Cnas4Y8Y9QZfWAQngUmtXchrfjCiv5Qguup
"""
from __future__ import annotations

import unittest

import submap as sm
import txbarrier as txb
import txexpect as txe

# Confirmed dump. Remaining-account bin array is index 38, not account[2].
SIG = (
    "5dc37b6cdb71039203995e3ccb2c3fadf4e3cff50e51af98cf61f0c3075df09f"
    "798f04826fd1eba078527830ad361e5c4cde5319ec60a7881d9fdc20fe56bf0f"
)
PAIR = "GYqytuXSiX3GaPuCkLMY4jeRR3mAtyAuQqhD32d45g5y"
BIN = "8BMU2qbuTZJAp1BETTpCKu5zWZ3L9fFX8ys5rAP2w9kE"
RESERVE = "5HUsU653znmCuEqK9rk6N3D1VsBCpYVuhKaLZ1GpPZ4v"
IDX = 26


class Pub:
    def __init__(self) -> None:
        self.gen = 0
        self.s = None
        self.barrier = txb.TxBarrier()
        self.barrier.note_tx(SIG, 450482164, {
            IDX: {"expected": {PAIR, BIN}, "kind": "dlmm", "pubkey": PAIR,
                  "variant": "dlmm_swap1"},
        })

    def write(self, pk: str) -> None:
        self.barrier.note_write(SIG, 450482164, IDX, pk)
        if self.barrier.can_commit(SIG, IDX):
            self.gen += 1
            self.s = {"active_id": 2727, "bins": {2727: (516034070, 283813495)}}


class TestExpect(unittest.TestCase):
    def test_swap1_expected_is_pair_and_remaining_bin(self):
        accs = [
            PAIR, txe.DLMM, RESERVE,
            "8rdFaxcGmi9V7J5nuT3PQJxcFvYS3c8kQrNniT9hW14t",
            "5B1yfnAXRxNtGzDeYrbde9yT9b8apNML2HckRwyu4oGj",
            "5tmiuBEEzD3zE4RqgHPEBDznNawYmojFJwRLfbJSNwAk",
            "METvsvVRapdj9cFLzq4Tr43xK4tAjQfwX76z3n6mWQL",
            "So11111111111111111111111111111111111111112",
            "3onGEdZWHZLv4sWAfaMdTbmaU6x2RVe3UfRQhCLStJVN",
            txe.DLMM,
            "9nXDunV8eNvYSVys7JSBkm2hz9Q79Q3EYeko19srVeMC",
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "D1ZN9Wj1fRSUQfCjhvnu1hqDMT7hzjzBBpi12nVniYD6",
            txe.DLMM,
            BIN,
        ]
        deps = {
            PAIR: [{"pool_idx": IDX, "role": sm.ROLE_DLMM_PAIR}],
            BIN: [{"pool_idx": IDX, "role": sm.ROLE_DLMM_BIN}],
        }
        exp = txe.expected_for_ix("dlmm", accs, IDX, deps)
        self.assertIn(PAIR, exp)
        self.assertIn(BIN, exp)
        self.assertNotIn(RESERVE, exp)

    def test_tx_exact_swap1(self):
        st = txe.tx_exact_status([{
            "program": txe.DLMM,
            "data": bytes.fromhex("f8c69e91e17587c8") + bytes(16),
        }])
        self.assertTrue(st["tx_exact"])

    def test_classify_swap1(self):
        self.assertEqual(
            txe.classify_ix(txe.DLMM, bytes.fromhex("f8c69e91e17587c8") + bytes(16)),
            "dlmm_swap1",
        )


class TestBarrierOrder(unittest.TestCase):
    def test_pair_then_bin(self):
        p = Pub()
        self.assertEqual(p.gen, 0)
        p.write(PAIR)
        self.assertEqual(p.gen, 0)
        self.assertIsNone(p.s)
        p.write(BIN)
        self.assertEqual(p.gen, 1)
        self.assertEqual(p.s["active_id"], 2727)

    def test_bin_then_pair(self):
        p = Pub()
        p.write(BIN)
        self.assertEqual(p.gen, 0)
        p.write(PAIR)
        self.assertEqual(p.gen, 1)
        self.assertEqual(p.s["bins"][2727], (516034070, 283813495))

    def test_same_final_state_either_order(self):
        a, b = Pub(), Pub()
        a.write(PAIR)
        a.write(BIN)
        b.write(BIN)
        b.write(PAIR)
        self.assertEqual(a.gen, b.gen)
        self.assertEqual(a.s, b.s)

    def test_slot_boundary_incomplete_does_not_commit(self):
        p = Pub()
        p.write(PAIR)
        dead = p.barrier.expire_at_boundary(450482165)
        self.assertEqual(dead, [(SIG, IDX)])
        self.assertFalse(p.barrier.can_commit(SIG, IDX))
        self.assertEqual(p.gen, 0)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
