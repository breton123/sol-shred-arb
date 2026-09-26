#!/usr/bin/env python3
import unittest

from reduce_buy013 import fee, pred_buy_quote


class Buy013(unittest.TestCase):
    def test_idx216_proto_only(self):
        sb = {"lp_fee_bps": 20, "protocol_fee_bps": 5, "creator_fee_bps": 5}
        ain = 100000000
        pred, f = pred_buy_quote(sb, ain)
        self.assertEqual(pred, 99900298)
        self.assertEqual(f["proto"], 49851)
        pub = 99950149
        self.assertEqual(pred - pub, -f["proto"])
        self.assertEqual(ain - f["proto"], pub)

    def test_pool_creator_100_identity(self):
        ain = 262226
        lp, pr, cr = 20, 5, 100
        tot = lp + pr + cr
        eff = ain * 10000 // (10000 + tot)
        got = ain - fee(eff, pr) - fee(eff, cr)
        # committed vault on the SCOREBOARD-style DJT sample was 259506
        self.assertEqual(got, 259506)


if __name__ == "__main__":
    unittest.main()
