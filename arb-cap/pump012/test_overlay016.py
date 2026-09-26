#!/usr/bin/env python3
import unittest

from pump_apply import apply_swap
from pump_overlay import (
    MODEL,
    apply_buy_exact_out,
    apply_cpi,
    apply_sequence,
    cpi_id,
    classify_overlay,
)


def _s(rb=10**12, rq=10**15, v=0, lp=20, pr=5, cr=5):
    return {
        "reserve_base": rb, "reserve_quote": rq, "virtual_quote": v,
        "virtual_quote_reserves": v, "lp_fee_bps": lp, "protocol_fee_bps": pr,
        "creator_fee_bps": cr, "status": 0,
    }


class Overlay016(unittest.TestCase):
    def test_buy_exact_out_moves_exact_base(self):
        s = _s()
        base_out = 10**6
        g = apply_buy_exact_out(s, base_out)
        self.assertIsNotNone(g)
        self.assertEqual(g["reserve_base"], s["reserve_base"] - base_out)

    def test_two_leg_net_is_composition(self):
        s = _s()
        sell_n = 11411288817
        buy_out = 11345137575
        a = apply_cpi(s, {"kind": "sell", "amount": sell_n})
        self.assertIsNotNone(a)
        b = apply_cpi(a, {"kind": "buy_exact_out", "amount": buy_out})
        self.assertIsNotNone(b)
        self.assertEqual(b["reserve_base"] - s["reserve_base"], sell_n - buy_out)

    def test_unknown_cpi_fail_closed(self):
        s = _s()
        term, fail = apply_sequence(s, [{"kind": "unknown", "amount": 1}])
        self.assertIsNone(term)
        self.assertEqual(fail, "unsupported_cpi")

    def test_empty_is_association(self):
        term, fail = apply_sequence(_s(), [])
        self.assertEqual(fail, "association_ambiguity")

    def test_never_n_from_published(self):
        # composition uses ix amounts, not vault delta as N
        s = _s()
        a = apply_cpi(s, {"kind": "sell", "amount": 1000})
        pub_delta = a["reserve_base"] - s["reserve_base"]
        self.assertEqual(pub_delta, 1000)
        self.assertNotEqual(MODEL, "n_equals_vault_delta")

    def test_identity_fields(self):
        c = cpi_id("sig", {
            "outer_ix": 5, "inner_ordinal": 3, "pool": "P",
            "direction": 1, "src_ata": "S", "dst_ata": "D", "kind": "sell",
        })
        self.assertEqual(c["outer_ix"], 5)
        self.assertEqual(c["inner_ordinal"], 3)
        self.assertEqual(c["model_version"], MODEL)

    def test_classify_bit_exact(self):
        s = _s()
        g = apply_swap(s, 1000, 1)
        self.assertEqual(
            classify_overlay(s, g, g, None, [{"kind": "sell"}]),
            "bit_exact",
        )


if __name__ == "__main__":
    unittest.main()
