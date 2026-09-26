import struct
import unittest
from bank_context import BankJournal, SYSVAR_OWNER, parse_slot_hashes


def event(kind, rx, **fields):
    return dict(kind=kind, rx=rx, generation="connection-a", slot=101, bank_id=7, **fields)


def account(rx=2, **override):
    r = event("bank_account", rx, owner=SYSVAR_OWNER, startup=False,
              data_hex=struct.pack("<QQ32s", 1, 100, bytes([3])*32).hex())
    return dict(r, **override)


class BankContextTests(unittest.TestCase):
    def setUp(self):
        self.j = BankJournal()
        self.j.apply({"kind": "bank_generation", "generation": "connection-a", "rx": 0})

    def ctx(self, deadline=10, bank_id=7, generation="connection-a", slot=101):
        return self.j.context(slot, bank_id, generation, deadline)

    def test_deadline_and_identity_are_required(self):
        self.j.apply(account())
        self.assertEqual(self.ctx()["reason"], "context_incomplete")
        self.j.apply(event("bank_slot", 3, parent=100, status=5))
        self.assertEqual(self.ctx(2)["reason"], "not_available_at_deadline")
        self.assertEqual(self.ctx()["reason"], "available")
        self.assertEqual(self.ctx(bank_id=None)["reason"], "identity_missing")
        self.assertEqual(self.ctx(bank_id=8)["reason"], "context_missing")
        self.assertEqual(self.ctx(generation="rabbit")["reason"], "generation_unbound")

    def test_reconnect_cannot_reuse_bank_ids(self):
        self.j.apply(account())
        self.j.apply(event("bank_slot", 3, parent=100, status=0))
        self.j.apply({"kind": "bank_generation", "generation": "connection-b", "rx": 4})
        self.assertEqual(self.j.apply(account(5)), "stale_generation")
        self.assertEqual(self.ctx(generation="connection-b")["reason"], "context_missing")
        self.j.apply({"kind": "bank_disconnect", "generation": "connection-b", "rx": 6})
        self.assertEqual(self.ctx(generation="connection-b")["reason"], "generation_unbound")

    def test_conflicts_and_dead_banks_cannot_heal(self):
        self.j.apply(account())
        self.j.apply(event("bank_slot", 3, parent=100, status=0))
        before = self.ctx()
        self.j.apply(event("bank_slot", 4, parent=100, status=6))
        self.j.apply(event("bank_slot", 5, parent=100, status=2))
        self.assertEqual(self.ctx()["reason"], "dead_bank")
        self.assertEqual(before["context"]["statuses"], [0])
        self.j.apply(event("bank_slot", 6, parent=99, status=5))
        self.assertEqual(self.ctx()["reason"], "context_conflict")

    def test_malformed_sysvar_and_startup_are_rejected(self):
        self.assertEqual(self.j.apply(account(startup=True)), "invalid_sysvar_provenance")
        self.assertEqual(self.ctx()["reason"], "context_conflict")
        with self.assertRaises(ValueError): parse_slot_hashes(bytes(7))
        with self.assertRaises(ValueError): parse_slot_hashes(struct.pack("<Q", 513))
        with self.assertRaises(ValueError): parse_slot_hashes(struct.pack("<QQ32sQ32s", 2, 1, bytes(32), 2, bytes(32)))

    def test_missing_optional_parent_does_not_become_slot_zero(self):
        self.j.apply(account())
        self.j.apply(event("bank_slot", 3, parent=None, status=0))
        self.assertEqual(self.ctx()["reason"], "context_incomplete")
        self.j.apply(event("bank_slot", 4, parent=100, status=0))
        self.assertEqual(self.ctx()["reason"], "available")

    def test_empty_ancestors_cannot_certify_a_non_genesis_bank(self):
        self.j.apply(account(data_hex=struct.pack("<Q", 0).hex()))
        self.j.apply(event("bank_slot", 3, parent=100, status=0))
        self.assertEqual(self.ctx()["reason"], "context_incomplete")

    def test_out_of_order_receipts_quarantine_the_bank(self):
        self.j.apply(account(3))
        self.assertEqual(self.j.apply(event("bank_slot", 2, parent=100, status=0)),
                         "receipt_order_conflict")
        self.j.apply(event("bank_slot", 4, parent=100, status=0))
        self.assertEqual(self.ctx()["reason"], "context_conflict")


if __name__ == "__main__": unittest.main()
