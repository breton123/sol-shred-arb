"""Restricted model admission and rollback interpretation, entirely offline."""
import base64
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import route_snapshot as m


def account(data,owner=m.TOKEN22):
    return {'owner':owner,'data':[base64.b64encode(data).decode(),'base64']}


def mint(extension=18,length=64):
    raw=bytearray(166);raw[45]=1;raw[165]=1
    return raw+struct.pack('<HH',extension,length)+bytes(length)


class SnapshotTests(unittest.TestCase):
    def test_metadata_only_mint_is_allowed(self):
        data,types=m.token_data(account(mint()),True)
        self.assertEqual(types,[18]);self.assertEqual(len(data),234)

    def test_transfer_fee_and_hook_are_not_silently_zero(self):
        for extension in (1,14,99):
            with self.assertRaisesRegex(ValueError,'unsupported'):m.token_data(account(mint(extension)),True)

    def test_malformed_and_duplicate_extensions_reject(self):
        for data in (mint()[:-1],mint()+struct.pack('<HH',18,0)):
            with self.assertRaises(ValueError):m.token_data(account(data),True)
        data=mint();data[90]=1
        with self.assertRaisesRegex(ValueError,'header'):m.token_data(account(data),True)

    def test_frozen_account_and_wrong_account_type_reject(self):
        data=bytearray(170);data[108]=2;data[165]=2;struct.pack_into('<HH',data,166,7,0)
        with self.assertRaisesRegex(ValueError,'frozen'):m.token_data(account(data))
        data[108]=1;self.assertEqual(m.token_data(account(data))[1],[7])
        data[165]=1
        with self.assertRaisesRegex(ValueError,'header'):m.token_data(account(data))

    def test_clock_must_match_single_snapshot(self):
        clock=bytearray(40);struct.pack_into('<Q',clock,0,9)
        with self.assertRaisesRegex(ValueError,'clock_context'):
            m.quote_snapshot({m.CLOCK:account(clock,m.SYSVAR)},10,
                             {'keys':['x']*10,'hops':[{}, {'accounts':[]}]},{})

    def value(self,error=True):
        def transfer(source,dest,amount):
            return {'programId':m.TOKEN,'parsed':{'type':'transfer','info':{
                'source':source,'destination':dest,'amount':str(amount)}}}
        return {'err':{'InstructionError':[2,{'Custom':6}]} if error else None,
                'logs':[f'Program {m.wire.DLMM} success',f'Program {m.pump_fee.PUMP_AMM} success',
                        'Program executor failed: custom program error: 0x6'],
                'innerInstructions':[{'instructions':[transfer('Q','vault',100),transfer('vault','B',300),
                    transfer('B','vault',300),transfer('vault','Q',95)]}]}

    def test_rollback_transfers_are_transient_not_profit(self):
        result=m.transient_cycle_amounts(self.value(),'Q','B','executor')
        self.assertEqual(result['gross_before_guard'],-5)
        self.assertFalse(result['committed'])

    def test_incomplete_or_failing_venue_trace_is_unknown(self):
        value=self.value();value['logs'].append(f'Program {m.wire.DLMM} failed: custom program error: 0x1')
        self.assertIsNone(m.transient_cycle_amounts(value,'Q','B','executor'))
        value=self.value();value['innerInstructions'][0]['instructions'][0]['parsed']['type']='syncNative'
        self.assertIsNone(m.transient_cycle_amounts(value,'Q','B','executor'))
        value=self.value();value['innerInstructions'][0]['instructions'].pop(2)
        self.assertIsNone(m.transient_cycle_amounts(value,'Q','B','executor'))

    def test_arbitrary_failure_cannot_be_called_profit_guard(self):
        value=self.value();value['err']={'InstructionError':[2,{'Custom':3005}]}
        self.assertIsNone(m.transient_cycle_amounts(value,'Q','B','executor'))


if __name__=='__main__':unittest.main()
