"""Offline executor-message and net-cost regression checks; no credentials/RPC."""
import json
from pathlib import Path
import struct
import sys
import unittest

from solders.hash import Hash
from solders.null_signer import NullSigner
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from hops_message import compile_message, net_economics


class HopsMessageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((Path(__file__).parent/"golden_hops/dp.json").read_text())
        self.keys = self.fixture["keys"]
        self.data = bytearray(40)
        self.data[:8] = b"ARBHOPS0"
        self.data[8] = 2
        struct.pack_into("<QQ",self.data,9,10000,5000)
        self.data[25:31] = bytes([1,0,1,2,1,0])
        self.data[34:36] = bytes([10,24])

    def message(self, alts=(), price=1):
        return compile_message(self.keys[0], str(Pubkey.default()), self.keys,
                               bytes(self.data), alts, 400000, Hash.default(),price)

    def test_zero_signature_roundtrip_and_fee_bid(self):
        msg = self.message(price=1000000)
        tx = VersionedTransaction(msg,[NullSigner(Pubkey.from_string(self.keys[0]))])
        parsed = VersionedTransaction.from_bytes(bytes(tx))
        self.assertEqual([bytes(s) for s in parsed.signatures],[bytes(64)])
        self.assertEqual(parsed.message.header.num_required_signatures,1)
        self.assertEqual(bytes(msg.instructions[0].data),b'\x02'+struct.pack('<I',400000))
        self.assertEqual(bytes(msg.instructions[1].data),b'\x03'+struct.pack('<Q',1000000))

    def test_two_luts_preserve_exact_executor_logical_order(self):
        unique=list(dict.fromkeys(self.keys[1:]))
        alts=[{"pubkey":str(Pubkey.from_bytes(bytes([i])*32)),"addresses":unique[i::2]} for i in range(2)]
        msg=self.message(alts)
        tables={a['pubkey']:a['addresses'] for a in alts}
        writable=[];readonly=[]
        for lookup in msg.address_table_lookups:
            addresses=tables[str(lookup.account_key)]
            writable.extend(addresses[i] for i in lookup.writable_indexes)
            readonly.extend(addresses[i] for i in lookup.readonly_indexes)
        resolved=[str(k) for k in msg.account_keys]+writable+readonly
        self.assertEqual([resolved[i] for i in msg.instructions[2].accounts],self.keys)
        self.assertEqual(bytes(msg.instructions[2].data),bytes(self.data))
        self.assertEqual(len(msg.address_table_lookups),2)

    def test_invalid_payer_and_payload(self):
        with self.assertRaises(ValueError):
            compile_message(str(Pubkey.default()),str(Pubkey.default()),self.keys,bytes(self.data),[],400000,Hash.default())
        self.data[0]=0
        with self.assertRaises(ValueError): self.message()

    def test_unknown_economics_stays_unknown(self):
        result=net_economics(None,405000,405000)
        self.assertIsNone(result['expected_net'])
        self.assertIsNone(result['conditional_success_net'])
        self.assertIsNone(net_economics(900000,405000,405000)['expected_net'])

    def test_success_and_charged_failure_costs(self):
        result=net_economics(1100000,405000,405000,150000,0,50000,5000,5000)
        self.assertEqual(result['expected_net'],20000)
        self.assertEqual(result['break_even_gross'],1060000)
        self.assertEqual(result['conditional_success_net'],495000)

    def test_uncharged_drop_is_not_charged_failure(self):
        result=net_economics(1100000,405000,405000,150000,0,50000,5000,0)
        self.assertEqual(result['expected_net'],222500)
        self.assertEqual(net_economics(99,5,7,0,0,2,0,10000)['expected_net'],-9)

    def test_invalid_probabilities_and_negative_costs(self):
        for p,f in [(9000,2000),(-1,0),(True,0),(0,10001)]:
            with self.assertRaises(ValueError): net_economics(1,1,1,success_bps=p,charged_failure_bps=f)
        with self.assertRaises(ValueError): net_economics(1,-1,1)

    def test_rounding_is_conservative(self):
        result=net_economics(1,0,1,success_bps=1,charged_failure_bps=1)
        self.assertEqual(result['expected_net'],0)
        self.assertEqual(result['break_even_gross'],1)
        self.assertEqual(net_economics(0,0,1,success_bps=1,charged_failure_bps=1)['expected_net'],-1)


if __name__ == '__main__': unittest.main()
