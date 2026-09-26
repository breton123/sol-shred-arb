from __future__ import annotations

import struct
import unittest

from inventory import BIN_SIZE, pack_bin
from state011_draft import FN_TYPE_OFF, parse_function_type, parse_orders_gate, published_s


def _pair(function_type: int = 2, reward0: bytes | None = None) -> bytes:
    raw = bytearray(904)
    raw[FN_TYPE_OFF] = function_type
    if reward0:
        from state011_draft import REWARD0_MINT
        raw[REWARD0_MINT : REWARD0_MINT + 32] = reward0
    return bytes(raw)


def _bin_array(index: int, bins: list[bytes]) -> bytes:
    body = bytearray(48 + 70 * BIN_SIZE)
    struct.pack_into("<q", body, 0, index)
    for i, b in enumerate(bins):
        body[48 + i * BIN_SIZE : 48 + (i + 1) * BIN_SIZE] = b
    return b"\x00" * 8 + bytes(body)


class GateAndSnap(unittest.TestCase):
    def test_function_type_offset_matches_parse_lbpair_layout(self):
        p = _pair(2)
        self.assertEqual(parse_function_type(p), 2)

    def test_ft0_reward_mask(self):
        p = _pair(0, reward0=b"\x01" * 32)
        g = parse_orders_gate(p)
        self.assertEqual(g["reward_mint_live_mask"], 1)
        self.assertFalse(g["orders_enabled"])
        p2 = _pair(0)
        self.assertTrue(parse_orders_gate(p2)["orders_enabled"])

    def test_published_s_sees_open_when_xy_unchanged(self):
        raw = _bin_array(0, [pack_bin(amount_x=111, amount_y=222, open_order_amount=50)])
        s0 = published_s(_pair(), [raw], 0)
        raw2 = _bin_array(0, [pack_bin(amount_x=111, amount_y=222, open_order_amount=80)])
        s1 = published_s(_pair(), [raw2], 0)
        self.assertEqual(s0["bins"][0]["x"], s1["bins"][0]["x"])
        self.assertEqual(s0["bins"][0]["y"], s1["bins"][0]["y"])
        self.assertNotEqual(s0["bins"][0]["open"], s1["bins"][0]["open"])


if __name__ == "__main__":
    unittest.main()
