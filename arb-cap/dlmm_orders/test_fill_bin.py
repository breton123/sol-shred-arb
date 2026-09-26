"""Quote AND post-bin state. Threshold transitions. No soak, no fill_mm edit."""
from __future__ import annotations

import unittest

from fill_bin import OBin, OState, apply_swap, bin_snap, fill_bin
from inventory import FN_LIQUIDITY_MINING, FN_UNDETERMINED


def st(**kw) -> OState:
    b = OBin(
        id=kw.pop("id", 0),
        amount_x=kw.pop("amount_x", 0),
        amount_y=kw.pop("amount_y", 0),
        processed_order_remaining_amount=kw.pop("proc", 0),
        open_order_amount=kw.pop("open", 0),
        limit_order_ask_side=kw.pop("ask", 0),
    )
    reserve_y = kw.pop("reserve_y", b.amount_y + b.processed_order_remaining_amount + b.open_order_amount)
    return OState(bins=[b], reserve_y=reserve_y, **kw)


class Thresholds(unittest.TestCase):
    def test_mm_sufficient_orders_untouched(self):
        s = st(amount_y=100, proc=40, open=50)
        after, q = apply_swap(s, 20, True)
        self.assertEqual(q["amount_out"], 20)
        self.assertEqual(bin_snap(after.bins[0]), {
            "id": 0, "amount_x": 20, "amount_y": 80,
            "processed_order_remaining_amount": 40,
            "open_order_amount": 50, "limit_order_ask_side": 0,
        })

    def test_mm_exhausted_then_processed(self):
        s = st(amount_y=20, proc=10, open=30)
        after, q = apply_swap(s, 25, True)
        self.assertEqual(q["amount_out"], 25)
        b = after.bins[0]
        self.assertEqual(b.amount_y, 0)
        self.assertEqual(b.processed_order_remaining_amount, 5)
        self.assertEqual(b.open_order_amount, 30)
        self.assertEqual(b.amount_x, 20)

    def test_processed_exhausted_then_open(self):
        s = st(amount_y=20, proc=10, open=30)
        after, q = apply_swap(s, 35, True)
        self.assertEqual(q["amount_out"], 35)
        b = after.bins[0]
        self.assertEqual((b.amount_y, b.processed_order_remaining_amount, b.open_order_amount), (0, 0, 25))
        self.assertEqual(b.amount_x, 20)

    def test_all_three_consumed(self):
        s = st(amount_y=20, proc=10, open=30)
        after, q = apply_swap(s, 60, True)
        self.assertEqual(q["amount_out"], 60)
        b = after.bins[0]
        self.assertEqual((b.amount_y, b.processed_order_remaining_amount, b.open_order_amount), (0, 0, 0))
        self.assertEqual(b.amount_x, 20)

    def test_wrong_side_open_ignored(self):
        s = st(amount_y=5, open=10000, ask=1)
        after, q = apply_swap(s, 5, True)
        self.assertEqual(q["amount_out"], 5)
        self.assertEqual(after.bins[0].open_order_amount, 10000)
        with self.assertRaises(ValueError):
            apply_swap(s, 6, True)

    def test_function_type_lm_disables(self):
        s = st(amount_y=5, open=100, function_type=FN_LIQUIDITY_MINING)
        after, q = apply_swap(s, 5, True)
        self.assertEqual(q["amount_out"], 5)
        self.assertEqual(after.bins[0].open_order_amount, 100)
        with self.assertRaises(ValueError):
            apply_swap(s, 6, True)

    def test_function_type_zero_conditional(self):
        s = st(amount_y=1, open=50, function_type=FN_UNDETERMINED, reward_mint_live_mask=1)
        with self.assertRaises(ValueError):
            apply_swap(s, 2, True)
        s.reward_mint_live_mask = 0
        after, q = apply_swap(s, 2, True)
        self.assertEqual(q["amount_out"], 2)
        self.assertEqual(after.bins[0].open_order_amount, 49)

    def test_multiple_bins_with_orders(self):
        s = OState(
            active_id=1,
            reserve_y=14,
            bins=[
                OBin(id=0, open_order_amount=7),
                OBin(id=1, amount_y=3, open_order_amount=4),
            ],
        )
        after, q = apply_swap(s, 10, True)
        self.assertEqual(q["amount_out"], 10)
        self.assertEqual(after.active_id, 0)
        self.assertEqual(bin_snap(after.bins[1])["amount_y"], 0)
        self.assertEqual(bin_snap(after.bins[1])["open_order_amount"], 0)
        self.assertEqual(bin_snap(after.bins[0])["open_order_amount"], 4)

    def test_fake_max_out_patch_would_poison_s_prime(self):
        """amount_y -= 60 is wrong when 20/10/30 came from three layers."""
        s = st(amount_y=20, proc=10, open=30)
        after, q = apply_swap(s, 60, True)
        self.assertEqual(q["amount_out"], 60)
        self.assertNotEqual(after.bins[0].amount_y, 20 - 60)  # underflow / wrong model
        self.assertEqual(after.bins[0].amount_y, 0)

    def test_fill_bin_split(self):
        b = OBin(amount_y=20, processed_order_remaining_amount=10, open_order_amount=30)
        f = fill_bin(b, 60, True, True)
        self.assertEqual((f.mm_out, f.proc_out, f.open_out), (20, 10, 30))


if __name__ == "__main__":
    unittest.main()
