"""Prove CORE-003 MM-only vs official available_output. No soak, no kernel edit."""
from __future__ import annotations

import unittest

from inventory import (
    available_output,
    fill_layers,
    is_support_limit_order,
    kernel_available_output,
    limit_order_amounts_by_direction,
    mm_unchanged,
    pack_bin,
    parse_bin,
    placement_delta,
)


def bid(**kw):
    kw.setdefault("limit_order_ask_side", 0)
    return kw


def ask(**kw):
    kw.setdefault("limit_order_ask_side", 1)
    return kw


class OfficialFormula(unittest.TestCase):
    def test_available_is_mm_plus_open_plus_processed_remaining(self):
        b = bid(amount_x=1, amount_y=10, open_order_amount=3, processed_order_remaining_amount=4)
        self.assertEqual(available_output(b, True), 10 + 3 + 4)
        self.assertEqual(kernel_available_output(b, True), 10)

    def test_total_processing_is_not_a_fillable_layer(self):
        b = bid(
            amount_y=0,
            open_order_amount=0,
            total_processing_order_amount=999,
            processed_order_remaining_amount=7,
        )
        self.assertEqual(available_output(b, True), 7)

    def test_bid_fills_on_swap_for_y_only(self):
        b = bid(amount_y=5, amount_x=8, open_order_amount=100)
        self.assertEqual(limit_order_amounts_by_direction(b, True), (100, 0))
        self.assertEqual(limit_order_amounts_by_direction(b, False), (0, 0))
        self.assertEqual(available_output(b, True), 105)
        self.assertEqual(available_output(b, False), 8)

    def test_ask_fills_on_swap_for_x_only(self):
        b = ask(amount_x=5, amount_y=8, open_order_amount=100)
        self.assertEqual(limit_order_amounts_by_direction(b, False), (100, 0))
        self.assertEqual(limit_order_amounts_by_direction(b, True), (0, 0))
        self.assertEqual(available_output(b, False), 105)
        self.assertEqual(available_output(b, True), 8)

    def test_support_flag_off_is_mm_only(self):
        b = bid(amount_y=2, open_order_amount=50, processed_order_remaining_amount=9)
        self.assertEqual(available_output(b, True, support_limit_order=False), 2)

    def test_function_type_gate(self):
        self.assertTrue(is_support_limit_order(2))
        self.assertFalse(is_support_limit_order(1))
        self.assertTrue(is_support_limit_order(0, True))
        self.assertFalse(is_support_limit_order(0, False))

    def test_fill_order_mm_then_processed_then_open(self):
        b = bid(amount_y=10, processed_order_remaining_amount=6, open_order_amount=4)
        self.assertEqual(
            fill_layers(b, 13, True),
            {"mm": 10, "processed_remaining": 3, "open": 0, "unfilled": 0},
        )
        self.assertEqual(
            fill_layers(b, 20, True),
            {"mm": 10, "processed_remaining": 6, "open": 4, "unfilled": 0},
        )


class KernelHole(unittest.TestCase):
    def test_zero_mm_nonzero_orders_is_invisible_to_kernel(self):
        b = bid(amount_x=0, amount_y=0, open_order_amount=1_000_000)
        self.assertEqual(kernel_available_output(b, True), 0)
        self.assertEqual(available_output(b, True), 1_000_000)

    def test_placement_can_leave_mm_xy_unchanged(self):
        before = bid(amount_x=111, amount_y=222, open_order_amount=0)
        after = bid(amount_x=111, amount_y=222, open_order_amount=50)
        d = placement_delta(before, after)
        self.assertTrue(mm_unchanged(d))
        self.assertEqual(d["open_order_amount"], 50)

    def test_wrong_side_orders_do_not_inflate_quote(self):
        b = ask(amount_y=1, open_order_amount=10_000)
        self.assertEqual(available_output(b, True), 1)
        self.assertEqual(kernel_available_output(b, True), 1)


class WireLayout(unittest.TestCase):
    def test_roundtrip_144(self):
        raw = pack_bin(
            amount_x=9,
            amount_y=8,
            open_order_amount=7,
            total_processing_order_amount=6,
            processed_order_remaining_amount=5,
            limit_order_ask_side=1,
            order_age=3,
        )
        self.assertEqual(len(raw), 144)
        p = parse_bin(raw)
        self.assertEqual(p["amount_x"], 9)
        self.assertEqual(p["amount_y"], 8)
        self.assertEqual(p["open_order_amount"], 7)
        self.assertEqual(p["total_processing_order_amount"], 6)
        self.assertEqual(p["processed_order_remaining_amount"], 5)
        self.assertEqual(p["limit_order_ask_side"], 1)
        self.assertEqual(p["order_age"], 3)


if __name__ == "__main__":
    unittest.main()
