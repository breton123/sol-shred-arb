"""Exercise actual STATE-008 methods with controlled worker completion order."""
from __future__ import annotations
import ast
from collections import Counter
from pathlib import Path
import queue
import threading
from types import SimpleNamespace as NS
import unittest
import uuid

import bank_context as bc
import shadow as sh
import txbarrier as txb


def event(kind="account", generation="new", **fields):
    return dict(kind=kind, provider_generation=generation, **fields)


def write(pk="pair", slot=101, generation="new", version=1):
    return event(pubkey=pk, slot=slot, write_version=version, data=b"stream", t_rx=1,
                 txn_sig=bytes([1])*64, generation=generation)


class TestGeneration(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name("state008.py")
        cls = next(n for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.ClassDef) and n.name=="State008")
        names = {"reset_connection", "rpc_row", "handle_event", "finish_bootstrap", "apply_update",
                 "pool_complete", "mark_ready", "fetch_async"}
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.env = dict(bc=bc, sh=sh, txb=txb, threading=threading, uuid=uuid, queue=queue,
                        ST_GAPPED=3, ST_COHERENT=2, ST_STAGING=1, ST_INCOMPLETE=0,
                        _mono=lambda:1, recon=NS(invalidate=lambda *a:None, plane=lambda *a:None),
                        READY=NS(write_text=lambda *a,**k:None))
        exec(compile(ast.Module(body=[cls], type_ignores=[]),str(path),"exec"),self.env)
        s = self.s = self.env["State008"]()
        s.provider_generation = "old"
        s.bootstrap_token = "old-job"
        s.bootstrap_done = True
        s.bootstrap_slot = s.stream_slot = 100
        s.bootstrapping = False
        s.ready = True
        s.q = queue.Queue()
        s.rf = None
        s.lock = threading.RLock()
        s.m = Counter()
        s.bytes = {"pair":write(generation="old",version=9_000_000_000)}
        s.rpc_floors = {"pair":100}
        s.last_wv = {"pair":9_000_000_000}
        s.seen = {("pair",101,9_000_000_000)}
        s.buf = [write(generation="old")]
        s.barrier = txb.TxBarrier()
        s.shadow = NS(pending={"old":1}, by_idx={1:["old"]})
        s.pools = {1:NS(idx=1, required={"pair"}, stage={"old":1}, staged=[1], last_s={"old":1},
                       last_blob=b"old", s_before={"old":1}, status=2)}
        s.proto_of = {1:1}
        s.acc_deps = {}
        s.revocations = []
        s.auth = NS(reset_history=lambda:s.revocations.append(1), set_ready=lambda *a,**k:None)
        s.mark_uncertain = lambda why:setattr(s,"ready",False)
        s._plane_json = lambda _:None
        s._pools_json = s._recount = lambda:None
        s.published = []
        s.try_publish = lambda rec,*args:s.published.append(rec.idx)
        s.maybe_publish = lambda _:None
        s.tx_events = []
        s.apply_tx = lambda row:s.tx_events.append(row)
        s.reset_connection("new","test connect")

    def test_reset_revokes_state_history_and_counter_namespace(self):
        s = self.s
        self.assertFalse(s.ready)
        self.assertIsNone(s.bootstrap_token)
        self.assertFalse(s.bytes or s.last_wv or s.seen or s.buf or s.shadow.pending)
        self.assertIsNone(s.pools[1].last_s)
        self.assertEqual(s.revocations, [1])
        s.apply_update(write(), from_buf=True)
        self.assertEqual(s.bytes["pair"]["write_version"], 1)

    def test_old_bootstrap_universe_and_dependency_results_cannot_mutate_new_session(self):
        for kind in ("bootstrap_plan","bootstrap_result","univ_result","dependency_result","account","tx"):
            self.assertEqual(self.s.handle_event(event(kind,generation="old")),"stale_generation")
        self.assertFalse(self.s.bytes or self.s.ready)

    def test_replaced_ticket_cannot_complete_same_connection_bootstrap(self):
        self.s.bootstrap_token = "retry"
        self.assertEqual(self.s.handle_event(event("bootstrap_result",token="first",accounts={})),"stale_bootstrap")
        self.assertFalse(self.s.bootstrap_done)

    def test_request_queues_are_isolated_between_connections(self):
        old = self.s.req_q
        self.s.reset_connection("next", "reconnect")
        self.s.req_q.put(("next", "subscription"))
        self.assertIsNot(old, self.s.req_q)
        self.assertTrue(old.empty())
        self.assertEqual(self.s.req_q.get_nowait(), ("next", "subscription"))

    def test_rpc_floor_is_per_account_and_tx_metadata_is_buffered(self):
        s = self.s
        s.bootstrap_token = "job"
        s.stream_slot = 115
        s.handle_event(write(slot=101))
        s.handle_event(event("tx",slot=101,parsed={"sig":"a"}))
        s.handle_event(event("bootstrap_result",token="job",accounts={
            "pair":{"data":b"rpc-old","slot":100}, "other":{"data":b"rpc-new","slot":110}}))
        self.assertEqual(s.bytes["pair"]["data"], b"stream")
        self.assertEqual(s.bootstrap_slot, 110)
        self.assertEqual(len(s.tx_events), 1)
        self.assertTrue(s.ready)
        self.assertEqual(s.buf, [])

    def test_same_slot_rpc_stream_order_is_unknown_and_cannot_erase_later_slot(self):
        s = self.s
        s.rpc_floors["pair"] = 100
        s.bytes["pair"] = {"data":b"rpc","slot":100}
        s.apply_update(write(slot=100), from_buf=True)
        self.assertNotIn("pair",s.bytes)
        s.apply_update(write(slot=101,version=2), from_buf=True)
        s.apply_update(write(slot=100), from_buf=True)
        self.assertEqual(s.bytes["pair"]["slot"], 101)

    def test_buffer_overflow_revokes_instead_of_discarding_half_the_journal(self):
        s = self.s
        s.bootstrap_token = "job"
        s.buf = [write()]*20000
        self.assertEqual(s.handle_event(write()),"bootstrap_buffer_overflow")
        self.assertIsNone(s.bootstrap_token)
        self.assertFalse(s.ready or s.buf)

    def test_rpc_finishing_after_disconnect_is_rejected(self):
        s = self.s
        entered, release = threading.Event(), threading.Event()
        requested_slot = s.stream_slot
        def rpc(keys, **kwargs):
            self.assertEqual(kwargs, {"commitment":"processed", "min_context_slot":requested_slot})
            entered.set()
            self.assertTrue(release.wait(2))
            return {"pair":{"slot":100,"data":b"stale-result"}}
        self.env["dep"] = NS(_chunk_get=rpc)
        s.fetch_async("dependency_result",["pair"])
        self.assertTrue(entered.wait(2))
        s.reset_connection(None,"disconnect")
        release.set()
        result = s.q.get(timeout=2)
        self.assertEqual(s.handle_event(result),"stale_generation")
        self.assertFalse(s.bytes or s.ready)
        s.mark_ready()
        self.assertFalse(s.ready)


if __name__=="__main__":unittest.main()
