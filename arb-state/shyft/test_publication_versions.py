"""No RPC: superseded writes must not pass a completed publication barrier."""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

import shadow
from txbarrier import TxBarrier

SIG = "11" * 64


def account(pk, data, **fields):
    return dict(pubkey=pk, data=data, slot=100, write_version=10,
                txn_sig=bytes.fromhex(SIG), provider_generation="feed-a", bank_id=7, **fields)


class PublicationVersions(unittest.TestCase):
    def setUp(self):
        self.b = TxBarrier()
        self.rows = {pk:account(pk, data) for pk,data in (("pair", b"pair-A"), ("bin", b"bin-A"))}
        for pk,row in self.rows.items(): self.b.note_write(SIG, 100, 1, pk, version=row)
        self.b.note_tx(SIG, 100, {1:{"expected":set(self.rows)}})

    def snapshot(self):
        return self.b.snapshot(SIG, 1, set(self.rows), self.rows)

    def test_completed_barrier_rejects_superseded_own_write(self):
        self.rows["pair"] = dict(self.rows["pair"], data=b"pair-B", txn_sig=bytes([2])*64, write_version=11)
        self.assertTrue(self.b.can_commit(SIG, 1))
        self.assertEqual(self.snapshot(), ("write_superseded", None))

    def test_snapshot_does_not_follow_latest_mutation(self):
        reason, frozen = self.snapshot()
        self.assertEqual(reason, "available")
        self.rows["pair"]["data"] = b"pair-B"
        self.assertEqual(frozen["pair"]["data"], b"pair-A")

    def test_identical_bytes_from_another_generation_do_not_match(self):
        self.rows["pair"] = dict(self.rows["pair"], provider_generation="feed-b")
        self.assertEqual(self.snapshot()[0], "write_superseded")

    def test_conflicting_same_signature_version_stays_quarantined(self):
        row = dict(self.rows["pair"], write_version=11)
        self.b.note_write(SIG, 100, 1, "pair", version=row)
        self.rows["pair"] = row
        self.assertEqual(self.snapshot()[0], "write_version_conflict")

    def test_unversioned_barrier_cannot_supply_a_snapshot(self):
        self.b = TxBarrier()
        self.b.note_tx(SIG, 100, {1:{"expected":set(self.rows)}})
        for pk in self.rows:self.b.note_write(SIG, 100, 1, pk)
        self.assertEqual(self.snapshot()[0], "write_identity_missing")

    def test_unknown_new_dependency_is_not_filled_by_later_state(self):
        reason, frozen = self.b.snapshot(SIG, 1, set(self.rows)|{"new-bin"}, self.rows)
        self.assertEqual((reason, frozen), ("account_missing", None))

    def test_write_only_traffic_cannot_retain_unbounded_versions(self):
        for i in range(4096):
            self.b.note_write(str(i), 101, 1, "pair", version=self.rows["pair"])
        self.assertEqual(len(self.b.by_sig), 4096)
        self.assertIsNone(self.b.spec(SIG, 1))
        self.assertEqual(self.snapshot(), ("writes_incomplete", None))
        self.assertEqual(self.b.m["evicted_transactions"], 1)

    def test_real_publication_method_uses_the_checked_snapshot(self):
        # Compile the actual method without importing RPC/service initialization.
        path = Path(__file__).with_name("state008.py")
        tree = ast.parse(path.read_bytes())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=="State008")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=="try_publish")
        env = dict(sh=shadow, ST_INCOMPLETE=0, ST_STAGING=1, _mono=lambda:1)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), env)
        calls, failures = [], []
        rec = SimpleNamespace(idx=1, required=set(self.rows), kind="pump", status=1,
                              stage={"sig":bytes.fromhex(SIG), "slot":100, "rx":1})
        def publish(rec, slot, rx, accounts):
            self.rows["pair"]["data"] = b"newer"
            calls.append(accounts["pair"]["data"])
            return True
        service = SimpleNamespace(pool_complete=lambda _:True, barrier=self.b, bytes=self.rows,
                                  m={"auth_predicted_exact":0}, publish_pump=publish,
                                  _fail_tx_incomplete=lambda *args:failures.append(args))
        env["try_publish"](service, rec, 100)
        self.assertEqual(calls, [b"pair-A"])
        self.assertEqual(failures, [])
        # Reset the barrier while retaining a newer shared byte image.
        self.b.note_tx(SIG, 100, {1:{"expected":set(self.rows)}})
        for pk,row in self.rows.items():
            old = dict(row, data=b"pair-A") if pk=="pair" else row
            self.b.note_write(SIG, 100, 1, pk, version=old)
        env["try_publish"](service, rec, 100)
        self.assertEqual(len(calls), 1)
        self.assertEqual(failures[-1][-1], "write_superseded")
        self.assertEqual(service.m["snapshot_rejections"], {"write_superseded":1})

    def test_dlmm_does_not_splice_a_later_rpc_bin_into_this_snapshot(self):
        path = Path(__file__).with_name("state008.py")
        cls = next(n for n in ast.parse(path.read_bytes()).body
                   if isinstance(n, ast.ClassDef) and n.name=="State008")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=="publish_dlmm")
        quoted, requested = [], []
        env = dict(ST_INCOMPLETE=0, _mono=lambda:1,
                   sm=SimpleNamespace(ROLE_DLMM_PAIR="pair", ROLE_DLMM_BIN="bin"),
                   d=SimpleNamespace(parse_lbpair=lambda _:dict(active_id=0)),
                   dep=SimpleNamespace(bin_keys_for_active=lambda *_:["new-bin"]),
                   snap_dlmm=lambda *args:quoted.append(args))
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), env)
        rec = SimpleNamespace(idx=1, pubkey="pair", required={"pair"}, status=1)
        service = SimpleNamespace(bytes=dict(self.rows),
                   acc_deps={"pair":[{"pool_idx":1,"role":"pair"}]},
                   add_required=lambda *_:True, subscribe_keys=lambda _:None,
                   fetch_async=lambda kind, keys:requested.append((kind, keys)))
        snapshot = {"pair":dict(self.rows["pair"])}
        self.assertFalse(env["publish_dlmm"](service, rec, 100, 1, snapshot))
        self.assertEqual(quoted, [])
        self.assertEqual(requested, [("dependency_result", ["new-bin"])])
        self.assertNotIn("new-bin", service.bytes)
        self.assertNotIn("new-bin", snapshot)

    def test_future_inherited_dependency_is_not_a_valid_prestate(self):
        self.rows["config"] = dict(self.rows["pair"], pubkey="config", slot=101)
        self.assertEqual(self.snapshot(), ("dependency_from_future_slot", None))


if __name__=="__main__":unittest.main()
