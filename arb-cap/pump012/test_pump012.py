#!/usr/bin/env python3
import unittest

from pump_apply import apply_swap, invert_virtual
from replay import replay_one


# Frozen SCOREBOARD example: sell, V=0 misses quote, V=17584505254 hits both vaults.
EX = {
    "kind": "pump",
    "bucket": "kernel_bug",
    "direction": 1,
    "amount_in": 3821401148,
    "s_before": {
        "kind": "pump",
        "reserve_base": 76677658655105,
        "reserve_quote": 299444518561,
        "lp_fee_bps": 20,
        "protocol_fee_bps": 5,
        "creator_fee_bps": 5,
        "disabled": 0,
    },
    "published_s": {
        "kind": "pump",
        "reserve_base": 76681480056253,
        "reserve_quote": 299428751103,
    },
}


class Pump012(unittest.TestCase):
    def test_parse_virtual_offset(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import live001 as live
        raw = bytearray(261)
        raw[43:75] = b"\x01" * 32
        raw[75:107] = b"\x02" * 32
        raw[139:171] = b"\x03" * 32
        raw[171:203] = b"\x04" * 32
        raw[245:261] = (17584505254).to_bytes(16, "little", signed=True)
        p = live.parse_pump_pool(bytes(raw))
        self.assertEqual(p["virtual_quote_reserves"], 17584505254)

    def test_v0_misses_example(self):
        g = apply_swap(EX["s_before"], EX["amount_in"], 1)
        self.assertEqual(g["reserve_base"], EX["published_s"]["reserve_base"])
        self.assertNotEqual(g["reserve_quote"], EX["published_s"]["reserve_quote"])

    def test_inverted_virtual_hits(self):
        v = invert_virtual(EX["s_before"], EX["amount_in"], 1, EX["published_s"])
        self.assertIsNotNone(v)
        g = apply_swap({**EX["s_before"], "virtual_quote": v}, EX["amount_in"], 1)
        self.assertEqual(g["reserve_base"], EX["published_s"]["reserve_base"])
        self.assertEqual(g["reserve_quote"], EX["published_s"]["reserve_quote"])
        self.assertEqual(g["virtual_quote"], v)

    def test_replay_explains_cluster(self):
        self.assertEqual(replay_one(EX), "explained_virtual")

    def test_v0_exact_stays_exact(self):
        before = {
            "reserve_base": 1000000, "reserve_quote": 1000000,
            "virtual_quote": 0, "lp_fee_bps": 20, "protocol_fee_bps": 5,
            "creator_fee_bps": 0, "status": 0,
        }
        g = apply_swap(before, 1000, 1)
        self.assertIsNotNone(g)
        row = {
            "kind": "pump", "bucket": "kernel_bug", "direction": 1, "amount_in": 1000,
            "s_before": before, "published_s": g,
        }
        self.assertEqual(replay_one(row), "still_exact_v0")

    def test_assoc_untouched(self):
        self.assertEqual(
            replay_one({"kind": "pump", "bucket": "wrong_transaction_association"}),
            "wrong_association",
        )


if __name__ == "__main__":
    unittest.main()
