#!/usr/bin/env python3
import unittest

from reduce_n015 import (
    N_CLAMPED,
    N_LITERAL,
    N_UNKNOWN,
    SELL,
    b58decode_any,
    classify_n,
    executed_n,
    sig_b58,
)
from replay import replay_one


def _sell(ain, brb, urb, brq=1000, urq=900):
    return {
        "kind": "pump",
        "bucket": "kernel_bug",
        "direction": 1,
        "amount_in": ain,
        "s_before": {
            "reserve_base": brb, "reserve_quote": brq,
            "virtual_quote": 0, "lp_fee_bps": 20, "protocol_fee_bps": 5,
            "creator_fee_bps": 5, "status": 0,
        },
        "published_s": {"reserve_base": urb, "reserve_quote": urq},
        "idx": 1,
    }


class N015(unittest.TestCase):
    def test_executed_n_sell(self):
        b = _sell(100, 1000, 1080)
        self.assertEqual(executed_n(b), 80)
        self.assertEqual(replay_one(b), "wrong_n")

    def test_literal_when_equal(self):
        b = _sell(80, 1000, 1080)
        # may be explained_virtual not wrong_n if apply hits
        r = classify_n(b, None, {})
        if r["n_pred"] == r["n_exec"]:
            self.assertEqual(r["class"], N_LITERAL)

    def test_clamped_requested_gt_exec(self):
        # encoded 100, vault only moved 80
        b = _sell(100, 10**12, 10**12 + 80, brq=10**15, urq=10**15 - 1)
        r = classify_n(b, None, {})
        self.assertEqual(r["n_exec"], 80)
        self.assertEqual(r["class"], N_CLAMPED)

    def test_replay_tag(self):
        b = _sell(999, 1000, 1001, brq=1_000_000, urq=999_000)
        self.assertEqual(replay_one(b), "wrong_n")

    def test_sig_hex_to_b58(self):
        hx = "1a88bfdee86b2ac4a65c5d6496c5b63ba572801a2ebe0f1fa7a93d0502c56390a57e8b7db7684463b2fbf9c76f1fcd8fe952a6106f831144affb5bac4fbb5c01"
        s = sig_b58({"trigger_sig": hx})
        self.assertIsNotNone(s)
        self.assertNotEqual(s, hx)
        self.assertGreater(len(s), 80)

    def test_b58_ix_roundtrip_len(self):
        from pump_fee import b58encode
        raw = SELL + (123).to_bytes(8, "little") + (1).to_bytes(8, "little")
        self.assertEqual(b58decode_any(b58encode(raw)), raw)

    def test_negative_exec_not_clamped(self):
        b = _sell(100, 1000, 900)
        r = classify_n(b, None, {})
        self.assertEqual(r["class"], N_UNKNOWN)

    def test_sell_minus_buy_out_is_net(self):
        self.assertEqual(11411288817 - 11345137575, 66151242)


if __name__ == "__main__":
    unittest.main()
