import base64
import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

from alt_rpc import ALT_PROGRAM, U64_MAX, fetch_record, merge_record, parse_record, slot_hash_entries, write_cache
from alt_plane import refresh_due
from b58 import b58decode, b58encode
from hist_funnel011 import resolve_loaded


def account():
    raw = struct.pack("<IQQBB32sH", 1, U64_MAX, 100, 1, 1, bytes([3])*32, 0) + bytes([4])*32 + bytes([5])*32
    return {"owner": ALT_PROGRAM, "data": [base64.b64encode(raw).decode(), "base64"]}


def record():
    return dict(parse_record(account(), b58encode), observed_slot=100,
                observed_bank_hash=b58encode(bytes([0x11])*32), commitment="finalized",
                received_unix_ns=123, quarantined=False)


class LifecycleTests(unittest.TestCase):
    def test_base58_and_multi_table_order(self):
        for raw in (bytes(32), bytes([0])*3 + bytes([255])*29, bytes([1])*32):
            self.assertEqual(b58decode(b58encode(raw)), raw)
        self.assertEqual(len(b58decode("1")), 1)
        p = {"versioned": True, "static_keys": ["s"], "lut_tables": [
            {"pk": "a", "wr": [1], "ro": [0]}, {"pk": "b", "wr": [0], "ro": [1]},
            {"pk": "a", "wr": [0], "ro": [1]}]}
        alts = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
        self.assertEqual(resolve_loaded(p, alts), (["s", "a1", "b0", "a0", "a0", "b1", "a1"], "resolved_uncertified"))
        p["lut_tables"][0]["ro"] = [5]
        self.assertEqual(resolve_loaded(p, alts), (["s"], "alt_index_unavailable"))

    def test_metadata_and_bank_hash_provenance(self):
        calls = []
        def rpc(url, method, params):
            calls.append((method, params))
            if len(calls) == 1:
                return {"result": {"context": {"slot": 100}, "value": account()}}
            hashes = struct.pack("<QQ32s", 1, 100, bytes([0x11])*32)
            val = {"owner": "Sysvar1111111111111111111111111111111111111",
                   "data": [base64.b64encode(hashes).decode(), "base64"]}
            return {"result": {"context": {"slot": 102}, "value": val}}
        rec = fetch_record(rpc, "unused", "table", b58encode)
        self.assertEqual(rec["observed_bank_hash"], record()["observed_bank_hash"])
        self.assertEqual(rec["last_extended_slot_start_index"], 1)
        self.assertEqual(calls[1][0], "getAccountInfo")
        self.assertEqual(calls[1][1][1]["minContextSlot"], 101)

    def test_conflicts_stay_quarantined(self):
        old, new = record(), record()
        new["addresses"][0] = b58encode(bytes([8])*32)
        result = merge_record(old, new)
        self.assertTrue(result["quarantined"])
        self.assertTrue(merge_record(result, old)["quarantined"])
        new = copy.deepcopy(old); new["observed_slot"] += 1
        new["addresses"].append(b58encode(bytes([9])*32))
        self.assertFalse(merge_record(old, new)["quarantined"])
        new = copy.deepcopy(old); new["observed_bank_hash"] = b58encode(bytes([0x12])*32)
        self.assertEqual(merge_record(old, new)["quarantine_reason"], "bank_identity_conflict")
        new = copy.deepcopy(old); new["last_extended_slot_start_index"] = 0
        self.assertEqual(merge_record(old, new)["quarantine_reason"], "extension_prefix_conflict")

    def test_retry_and_first_success_are_publishable(self):
        pk = b58encode(bytes([1])*32)
        cache, due, attempts = {}, {pk: 0}, {}
        def fail(*_): raise OSError("temporary")
        self.assertEqual(refresh_due(cache, due, attempts, "unused", 0, fail), (False, 0, 1))
        self.assertGreater(due[pk], 0)
        self.assertEqual(refresh_due(cache, due, attempts, "unused", 2, lambda *_: record()), (True, 1, 0))
        with tempfile.TemporaryDirectory() as td:
            jp, bp = Path(td)/"cache.json", Path(td)/"cache.bin"
            write_cache(cache, jp, bp, b58decode)
            self.assertEqual(bp.read_bytes()[:4], b"ALT2")
            self.assertEqual(json.loads(jp.read_text())[pk]["observed_slot"], 100)
            self.assertEqual(len(bp.read_bytes()), 8 + 36 + 136 + 64)
        self.assertEqual(refresh_due(cache, due, attempts, "unused", 32, lambda *_: None), (True, 1, 0))
        self.assertFalse(cache)

    def test_invalid_keys_cannot_replace_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            jp, bp = Path(td)/"cache.json", Path(td)/"cache.bin"
            bp.write_bytes(b"keep")
            with self.assertRaises(ValueError): write_cache({"1": record()}, jp, bp, b58decode)
            self.assertEqual(bp.read_bytes(), b"keep")


if __name__ == "__main__": unittest.main()
