"""Check acquisition context on the actual shared RPC helper without network."""
import importlib.util
from pathlib import Path
import unittest


class RpcContext(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[2]/'arb-cap/record_dlmm.py'
        spec=importlib.util.spec_from_file_location('context_recorder',path)
        self.d=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.d)

    def test_explicit_context_and_per_batch_floor(self):
        calls=[]
        def rpc(method,params,**kwargs):
            calls.append((method,params))
            return {'context':{'slot':105},'value':[{'data':['YQ==','base64'],'owner':'owner','lamports':1} for _ in params[0]]}
        self.d.rpc=rpc
        rows=self.d.get_multiple(['account']*101,commitment='processed',min_context_slot=100)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(c[1][1]=={'encoding':'base64','commitment':'processed','minContextSlot':100} for c in calls))
        self.assertTrue(all(r['slot']==105 and r['commitment']=='processed' for r in rows))

    def test_provider_cannot_return_older_context_or_partial_vector(self):
        for response in ({'context':{'slot':99},'value':[None]}, {'context':{'slot':100},'value':[]}):
            self.d.rpc=lambda *a,**k:response
            with self.assertRaises(RuntimeError):self.d.get_multiple(['account'],min_context_slot=100)

    def test_default_call_preserves_existing_rpc_policy(self):
        seen=[]
        self.d.rpc=lambda method,params,**kwargs:seen.append(params) or {'context':{'slot':1},'value':[None]}
        self.assertEqual(self.d.get_multiple(['account']),[None])
        self.assertEqual(seen[0][1],{'encoding':'base64'})


if __name__=='__main__':unittest.main()
