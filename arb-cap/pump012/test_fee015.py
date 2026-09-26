#!/usr/bin/env python3
import unittest

from pump_fee import (
    PUMP_FUN,
    WSOL,
    ZERO32,
    b58encode,
    buy_components,
    calculate_fee_tier,
    fee_bps,
    is_pump_pool,
    parse_fee_config,
    parse_global_config,
    pool_market_cap,
    pump_pool_authority,
    resolve_creator,
    schedule_fees,
    uses_sol_tiers,
)


class Fee015(unittest.TestCase):
    def test_canonical_pda_deterministic(self):
        mint = "So11111111111111111111111111111111111111112"
        a = pump_pool_authority(mint)
        self.assertEqual(len(a), 44)
        self.assertTrue(is_pump_pool(mint, a))
        self.assertFalse(is_pump_pool(mint, mint))

    def test_calculate_fee_tier_docs(self):
        tiers = [
            {"market_cap_lamports_threshold": 0, "fees": {"lp_fee_bps": 2, "protocol_fee_bps": 93, "creator_fee_bps": 30}},
            {"market_cap_lamports_threshold": 420 * 10**9, "fees": {"lp_fee_bps": 20, "protocol_fee_bps": 5, "creator_fee_bps": 95}},
        ]
        self.assertEqual(calculate_fee_tier(tiers, 1)["protocol_fee_bps"], 93)
        self.assertEqual(calculate_fee_tier(tiers, 420 * 10**9)["creator_fee_bps"], 95)
        self.assertEqual(calculate_fee_tier(tiers, 10**18)["lp_fee_bps"], 20)

    def test_pool_market_cap_docs(self):
        # quote * supply / base
        self.assertEqual(pool_market_cap(1_000_000_000, 200_000_000, 10**9), 5 * 10**9)

    def test_creator_zero_means_schedule(self):
        bps, src = resolve_creator(30, 0, True)
        self.assertEqual((bps, src), (30, "schedule"))
        bps, src = resolve_creator(30, 100, True)
        self.assertEqual((bps, src), (100, "pool"))
        bps, src = resolve_creator(30, 100, False)
        self.assertEqual((bps, src), (30, "schedule"))

    def test_noncanonical_uses_flat(self):
        cfg = {
            "flat_fees": {"lp_fee_bps": 25, "protocol_fee_bps": 5, "creator_fee_bps": 0},
            "fee_tiers": [{"market_cap_lamports_threshold": 0, "fees": {"lp_fee_bps": 2, "protocol_fee_bps": 93, "creator_fee_bps": 30}}],
            "stable_fee_tiers": [],
            "exotic_flat_fees": {"lp_fee_bps": 0, "protocol_fee_bps": 0, "creator_fee_bps": 0},
        }
        self.assertEqual(schedule_fees(cfg, False, WSOL, 1)["lp_fee_bps"], 25)
        self.assertEqual(schedule_fees(cfg, True, WSOL, 1)["protocol_fee_bps"], 93)

    def test_idx399_tier0_vault_and_split(self):
        # FeeConfig sol tier 0 + buyback 50% of protocol. Not a fitted 111.
        c = buy_components(126477, 2, 93, 30, 5000, "carve")
        self.assertEqual(c["vault"], 124940)
        self.assertEqual(c["protocol_gross"], 1162)
        self.assertEqual(c["protocol"], 581)
        self.assertEqual(c["buyback"], 581)
        self.assertEqual(c["creator"], 375)
        self.assertEqual(126477, 124940 + 581 + 581 + 375)

    def test_buy_components_kernel_identity(self):
        # Global 20/5/5 on 1e8 — same as test_buy013
        c = buy_components(100_000_000, 20, 5, 5, 0, "ignore")
        self.assertEqual(c["vault"], 99900298)
        self.assertEqual(c["protocol"], 49851)

    def test_idx399_conservation_still_holds(self):
        spendable = 126477
        vault = 124940
        self.assertEqual(spendable, vault + 581 + 581 + 375)

    def test_fee_config_roundtrip_min(self):
        # disc + bump + admin + flat + empty vecs + exotic
        disc = bytes([143, 52, 146, 187, 219, 123, 76, 155])
        bump = b"\x01"
        admin = bytes(32)
        flat = (20).to_bytes(8, "little") + (5).to_bytes(8, "little") + (0).to_bytes(8, "little")
        empty = (0).to_bytes(4, "little")
        raw = disc + bump + admin + flat + empty + empty + flat
        cfg = parse_fee_config(raw)
        self.assertEqual(cfg["flat_fees"]["lp_fee_bps"], 20)
        self.assertEqual(cfg["fee_tiers"], [])

    def test_global_recipients_layout(self):
        disc = bytes(8)
        admin = bytes(32)
        lp = (20).to_bytes(8, "little")
        proto = (5).to_bytes(8, "little")
        disable = b"\x00"
        recips = bytes(32 * 8)
        rest = bytes(800)
        raw = disc + admin + lp + proto + disable + recips + rest
        g = parse_global_config(raw)
        self.assertEqual(g["lp_fee_bps"], 20)
        self.assertEqual(g["protocol_fee_bps"], 5)
        self.assertEqual(len(g["protocol_fee_recipients"]), 8)

    def test_pfee_program_constant(self):
        self.assertTrue(PUMP_FUN.startswith("6EF8"))
        self.assertEqual(fee_bps(126477, 46), 582)

    def test_tier_gate_is_coin_creator(self):
        z = b58encode(ZERO32)
        self.assertFalse(uses_sol_tiers({"canonical": False, "coin_creator": z}, "coin_creator"))
        self.assertTrue(uses_sol_tiers({"canonical": False, "coin_creator": "FWomXNwJZTVq9HwvJrNLPykfEzL7GEmAyvdw42vV2exn"}, "coin_creator"))
        self.assertFalse(uses_sol_tiers({"canonical": False}, "isPumpPool"))


if __name__ == "__main__":
    unittest.main()
