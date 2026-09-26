#!/usr/bin/env python3
import unittest

from reduce_fee014 import expect_dq, quote_deltas, role_of


class Fee014(unittest.TestCase):
    def test_idx399_conservation(self):
        spendable = 126477
        vault = 124940
        atas = 581 + 581 + 375
        self.assertEqual(spendable, vault + atas)
        kernel_pc = 64 + 64
        self.assertEqual(atas - kernel_pc, 1409)

    def test_expect_dq_matches_kernel_buy(self):
        # Global 5/5/20 on 1e8 spendable from idx 216 dump
        self.assertEqual(expect_dq(100000000, 20, 5, 5), 99900298)

    def test_role_layout(self):
        accs = [f"k{i}" for i in range(22)]
        self.assertEqual(role_of("k8", accs), "pool_quote")
        self.assertEqual(role_of("k6", accs), "user_quote")
        self.assertEqual(role_of("k10", accs), "protocol_fee_ata")
        self.assertEqual(role_of("k17", accs), "coin_creator_vault_ata")

    def test_quote_deltas(self):
        tx = {
            "transaction": {"message": {"accountKeys": [
                {"pubkey": "user"}, {"pubkey": "vault"}, {"pubkey": "proto"},
            ]}},
            "meta": {
                "preTokenBalances": [
                    {"accountIndex": 0, "mint": "Q", "uiTokenAmount": {"amount": "1000"}},
                    {"accountIndex": 1, "mint": "Q", "uiTokenAmount": {"amount": "5000"}},
                    {"accountIndex": 2, "mint": "Q", "uiTokenAmount": {"amount": "0"}},
                ],
                "postTokenBalances": [
                    {"accountIndex": 0, "mint": "Q", "uiTokenAmount": {"amount": "0"}},
                    {"accountIndex": 1, "mint": "Q", "uiTokenAmount": {"amount": "5900"}},
                    {"accountIndex": 2, "mint": "Q", "uiTokenAmount": {"amount": "100"}},
                ],
            },
        }
        d = quote_deltas(tx, "Q")
        self.assertEqual(d["user"], -1000)
        self.assertEqual(d["vault"], 900)
        self.assertEqual(d["proto"], 100)


if __name__ == "__main__":
    unittest.main()
