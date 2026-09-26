#!/usr/bin/env python3
import unittest

import overlay_n as ov
import txexpect as txe


class OverlayN(unittest.TestCase):
    def test_two_leg_identities(self):
        pool = "P"
        sell = txe.PUMP_SELL + (1000).to_bytes(8, "little") + (1).to_bytes(8, "little")
        buy = txe.PUMP_BUY + (400).to_bytes(8, "little") + (10**12).to_bytes(8, "little")
        ixs = [
            {"program": txe.PUMP, "accounts": [pool] + ["u"] * 8, "data": sell,
             "outer_ix": 2, "inner_ordinal": 0},
            {"program": txe.PUMP, "accounts": [pool] + ["u"] * 8, "data": buy,
             "outer_ix": 2, "inner_ordinal": 7},
        ]
        cpis = ov.cpis_from_parsed(ixs, pool)
        self.assertEqual([c["kind"] for c in cpis], ["sell", "buy_exact_out"])
        self.assertEqual(cpis[0]["amount"], 1000)
        self.assertEqual(cpis[1]["amount"], 400)
        self.assertEqual(cpis[0]["inner_ordinal"], 0)

    def test_unknown_on_pool_fail_closed(self):
        pool = "P"
        ixs = [{"program": txe.PUMP, "accounts": [pool], "data": bytes(24)}]
        cpis = ov.cpis_from_parsed(ixs, pool)
        self.assertEqual(cpis[0]["kind"], "unknown")

    def test_other_pool_ignored(self):
        ixs = [{"program": txe.PUMP, "accounts": ["Q"], "data": txe.PUMP_SELL + bytes(16)}]
        self.assertEqual(ov.cpis_from_parsed(ixs, "P"), [])


if __name__ == "__main__":
    unittest.main()
