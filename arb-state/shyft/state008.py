#!/usr/bin/env python3
"""STATE-008 — complete, transaction-coherent pricing state.

A pool cannot be AUTH'd unless every account the quote kernel reads is
in the current coherent generation. FUNDED stays 0.
Does not touch recover_pda3.
"""
from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

import grpc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gen"))
sys.path.insert(0, str(HERE.resolve().parents[1].parent / "arb-cap"))
sys.path.insert(0, str(HERE.resolve().parents[1].parent / "arb-cap" / "pump012"))
sys.path.insert(0, str(Path("/home/louis/arb-cap")))
sys.path.insert(0, str(Path("/home/louis/arb-cap/pump012")))

import config  # noqa: E402
import deps as dep  # noqa: E402
import authpub as ap  # noqa: E402
import bank_context as bc  # noqa: E402
import recon  # noqa: E402
import shadow as sh  # noqa: E402
import submap as sm  # noqa: E402
import txexpect as txe  # noqa: E402
import txbarrier as txb  # noqa: E402
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402
import apply_n as an  # noqa: E402
import overlay_n as ov  # noqa: E402

try:
    import geyser_pb2
    import geyser_pb2_grpc
except ImportError:
    geyser_pb2 = None  # type: ignore
    geyser_pb2_grpc = None  # type: ignore

CAP = Path(os.environ.get("STATE008_CAP") or "/home/louis/captures/state008")
RECON_PATH = Path("/home/louis/captures/paper_orbit/recon.bin")
UNIV = Path("/home/louis/captures/paper_orbit/liveuniv.json")
PAPER_AUDIT = Path("/home/louis/captures/paper_orbit/opp_synced.jsonl")
READY = CAP / "READY"
PLANE = CAP / "PLANE.json"
METRICS = CAP / "METRICS.json"
POOLS = CAP / "POOLS.json"
ST_INCOMPLETE = 0
ST_STAGING = 1
ST_COHERENT = 2
ST_GAPPED = 3
ST_NAME = ("INCOMPLETE", "STAGING", "COHERENT", "GAPPED")

UNIV_POLL_S = 10.0
LAT_CAP = 8192


def _mono() -> int:
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _b58(raw: bytes) -> str:
    return d._pk(raw) if raw else ""


def _pct(v: list[int], p: float) -> int:
    if not v:
        return 0
    s = sorted(v)
    return s[int(p * (len(s) - 1))]


def snap_dlmm(pair_data: bytes, bin_datas: list[bytes]) -> dict | None:
    try:
        lb = d.parse_lbpair(pair_data)
    except Exception:
        return None
    bins: list[dict] = []
    for raw in bin_datas:
        bins.extend(d.parse_bin_array(raw))
    active = lb["active_id"]
    use = [b for b in bins if abs(b["id"] - active) <= live.K]
    if not use:
        return None
    return {
        "lb": lb,
        "bins": use,
        "reserve_x": sum(b["x"] for b in use),
        "reserve_y": sum(b["y"] for b in use),
    }


class PoolRec:
    __slots__ = (
        "idx", "kind", "pubkey", "required", "optional", "status",
        "stage", "upd_since", "gen", "last_s", "last_blob", "s_before", "staged", "active_id",
    )

    def __init__(self, row: dict) -> None:
        self.idx = int(row["idx"])
        self.kind = row["kind"]
        self.pubkey = row["pubkey"]
        self.required = {pk for pk, _ in row["required"]}
        self.optional = {pk for pk, _ in row.get("optional") or []}
        self.status = ST_INCOMPLETE
        self.stage: dict = {}
        self.upd_since = 0
        self.gen = 0
        self.last_s: dict | None = None
        self.last_blob: bytes | None = None
        self.s_before: dict | None = None
        self.staged: list = []
        self.active_id = row.get("active_id")


class State008:
    def __init__(self) -> None:
        self.q: queue.SimpleQueue = queue.SimpleQueue()
        self.req_q: queue.SimpleQueue = queue.SimpleQueue()
        self.j: queue.SimpleQueue = queue.SimpleQueue()
        self.stop = threading.Event()
        self.rf = recon.open_recon(RECON_PATH)
        self.bytes: dict[str, dict] = {}
        self.acc_deps: dict[str, list[dict]] = {}
        self.pools: dict[int, PoolRec] = {}
        self.proto_of: dict[int, int] = {}
        self.fees = (20, 5, 0, 0)
        self.stream_slot = 0
        self.bank_journal = bc.BankJournal()
        self.provider_generation = None
        self.bootstrap_token = None
        self.bootstrap_done = False
        self.rpc_floors: dict[str, int] = {}
        self.bootstrap_slot = 0
        self.bootstrapping = True
        self.ready = False
        self.buf: list[dict] = []
        self.last_wv: dict[str, int] = {}
        self.seen: set[tuple] = set()
        self.univ_n = 0
        self.univ_mtime = 0.0
        self.sub_keys: list[str] = []
        self.shadow = sh.ShadowGate()
        self.barrier = txb.TxBarrier()
        self.auth = ap.AuthPub()
        self.auth.open()
        self.lock = threading.RLock()
        self.m = {
            "updates": 0,
            "published": 0,
            "gaps": 0,
            "reconnects": 0,
            "decode_fail": 0,
            "dup": 0,
            "mismatch": 0,
            "exact": 0,
            "rpc_lag": 0,
            "shadow_n": 0,
            "dependencies_expected": 0,
            "dependencies_subscribed": 0,
            "dependencies_received": 0,
            "pool_complete": 0,
            "companion_wait": 0,
            "publish_wait_pair": 0,
            "publish_wait_bin": 0,
            "publish_wait_vault": 0,
            "publish_wait_shape": 0,
            "publish_incomplete_at_boundary": 0,
            "tx_rx": 0,
            "tx_exact_seen": 0,
            "tx_unknown_dex": 0,
            "fastsoak_predict": 0,
            "fastsoak_skip_no_auth": 0,
            "fastsoak_skip_apply": 0,
            "fastsoak_fail_closed": 0,
            "non_exact_reauth": 0,
            "auth_predicted_exact": 0,
            "auth_reconciled_unknown": 0,
            "unsupported_shape": 0,
            "lat_stage": [],
            "lat_pub": [],
        }
        CAP.mkdir(parents=True, exist_ok=True)

    def _lat(self, bucket: str, ns: int) -> None:
        if ns < 0:
            return
        b = self.m[bucket]
        b.append(ns)
        if len(b) > LAT_CAP:
            del b[: len(b) - LAT_CAP]

    def reset_connection(self, generation: str | None, why: str) -> None:
        """Caller holds the state lock; no network I/O may occur here."""
        self.mark_uncertain(why)
        self.auth.reset_history()
        if generation != self.provider_generation:
            # A cancelled request iterator must never consume the next
            # connection's subscriptions from a shared queue.
            self.req_q = queue.SimpleQueue()
        self.bank_journal = bc.BankJournal()
        if generation is not None:
            self.bank_journal.apply({"kind": "bank_generation", "generation": generation, "rx": _mono()})
        self.provider_generation = generation
        self.bootstrap_token = None
        self.bootstrap_done = False
        self.bootstrapping = True
        self.bootstrap_slot = self.stream_slot = 0
        self.bytes.clear()
        self.rpc_floors.clear()
        self.last_wv.clear()
        self.seen.clear()
        self.buf.clear()
        self.barrier = txb.TxBarrier()
        self.shadow.pending.clear()
        self.shadow.by_idx.clear()
        for rec in self.pools.values():
            rec.stage.clear()
            rec.staged.clear()
            rec.last_s = rec.last_blob = rec.s_before = None
            rec.status = ST_GAPPED
            recon.invalidate(self.rf, self.proto_of[rec.idx], rec.idx, _mono(), 0)

    def rpc_row(self, pk: str, row: dict) -> dict:
        return dict(row, pubkey=pk, write_version=0, t_rx=_mono(), txn_sig=None,
                    provider_generation=self.provider_generation, bank_id=None, source="rpc")

    def install_generation(self, gen: dict, fetched_extra: dict[str, dict] | None = None) -> list[str]:
        """Merge a derived generation. Returns newly required keys."""
        new_keys = []
        self.univ_n = int(gen.get("univ_n") or gen.get("n_pool") or 0)
        self.m["dependencies_expected"] = int(gen.get("n_required") or 0)
        for row in gen["pools"]:
            rec = self.pools.get(row["idx"])
            if rec is None:
                rec = PoolRec(row)
                self.pools[row["idx"]] = rec
                self.proto_of[row["idx"]] = (
                    live.PROTO_DLMM if row["kind"] == "dlmm" else live.PROTO_PUMP
                )
            else:
                rec.required |= {pk for pk, _ in row["required"]}
                rec.optional |= {pk for pk, _ in row.get("optional") or []}
                if row.get("active_id") is not None:
                    rec.active_id = row["active_id"]
            for pk, role in row["required"] + list(row.get("optional") or []):
                deps = self.acc_deps.setdefault(pk, [])
                if not any(x["pool_idx"] == row["idx"] and x["role"] == role for x in deps):
                    deps.append({
                        "pool_idx": row["idx"], "role": role,
                        "kind": row["kind"],
                        "required": (pk, role) in row["required"],
                    })
                if pk not in self.bytes:
                    new_keys.append(pk)
        if fetched_extra:
            for pk, a in fetched_extra.items():
                if pk in self.bytes:
                    continue
                self.bytes[pk] = self.rpc_row(pk, a)
                self.rpc_floors[pk] = int(a.get("slot") or 0)
        self._recount()
        return list(dict.fromkeys(new_keys))

    def _recount(self) -> None:
        recv = sum(1 for pk in self.acc_deps if pk in self.bytes and self.bytes[pk].get("data"))
        self.m["dependencies_received"] = recv
        self.m["dependencies_subscribed"] = len(self.sub_keys)
        for rec in self.pools.values():
            if rec.status == ST_COHERENT and not self.pool_complete(rec):
                rec.status = ST_INCOMPLETE
        self.m["pool_complete"] = sum(1 for r in self.pools.values() if r.status == ST_COHERENT)

    def pool_complete(self, rec: PoolRec) -> bool:
        if not rec.required:
            return False
        return all((self.bytes.get(pk) or {}).get("data") for pk in rec.required)

    def set_status(self, rec: PoolRec, st: int) -> None:
        rec.status = st
        if st == ST_GAPPED:
            self.m["gaps"] += 1

    def mark_uncertain(self, why: str) -> None:
        self.ready = False
        self.m["gaps"] += 1
        self.auth.set_ready(False, n_pools=len(self.pools), slot=self.stream_slot)
        recon.plane(self.rf, False, self.stream_slot)
        for rec in self.pools.values():
            if rec.status == ST_COHERENT:
                rec.status = ST_GAPPED
                recon.invalidate(self.rf, self.proto_of[rec.idx], rec.idx, _mono(), self.stream_slot)
        try:
            if READY.exists():
                READY.unlink()
            self._plane_json(why)
        except OSError:
            self.m["control_file_errors"] = self.m.get("control_file_errors", 0) + 1
        print(f"STATE-008  GAPPED  {why}", flush=True)

    def mark_ready(self) -> None:
        if self.provider_generation is None or not self.bootstrap_done:
            return
        self.ready = True
        self.bootstrapping = False
        READY.write_text("1\n", encoding="utf-8")
        self.auth.set_ready(True, n_pools=len(self.pools), slot=self.stream_slot)
        recon.plane(self.rf, True, self.stream_slot)
        self._plane_json("ready")
        print(
            f"STATE-008  READY  stream_slot={self.stream_slot} "
            f"bootstrap_slot={self.bootstrap_slot} "
            f"expected={self.m['dependencies_expected']} "
            f"subscribed={self.m['dependencies_subscribed']} "
            f"received={self.m['dependencies_received']} "
            f"complete={self.m['pool_complete']}/{len(self.pools)}",
            flush=True,
        )

    def _plane_json(self, why: str) -> None:
        by = defaultdict(int)
        for rec in self.pools.values():
            by[ST_NAME[rec.status]] += 1
        PLANE.write_text(json.dumps({
            "ready": self.ready,
            "why": why,
            "univ_n": self.univ_n,
            "dependencies_expected": self.m["dependencies_expected"],
            "dependencies_subscribed": self.m["dependencies_subscribed"],
            "dependencies_received": self.m["dependencies_received"],
            "pool_complete": self.m["pool_complete"],
            "n_pool": len(self.pools),
            "status": dict(by),
            "stream_slot": self.stream_slot,
            "bootstrap_slot": self.bootstrap_slot,
            "ts": _utc(),
        }, indent=2) + "\n", encoding="utf-8")

    def _pools_json(self) -> None:
        rows = []
        for rec in self.pools.values():
            rows.append({
                "idx": rec.idx, "kind": rec.kind, "pubkey": rec.pubkey,
                "status": ST_NAME[rec.status],
                "n_required": len(rec.required),
                "n_have": sum(1 for k in rec.required if k in self.bytes),
                "gen": rec.gen, "active_id": rec.active_id,
            })
        POOLS.write_text(json.dumps({"ts": _utc(), "pools": rows}, indent=2) + "\n")

    def subscribe_keys(self, keys: list[str]) -> None:
        self.sub_keys = list(dict.fromkeys(keys))
        self.m["dependencies_subscribed"] = len(self.sub_keys)
        if geyser_pb2 is None:
            return
        self.req_q.put((self.provider_generation, self._sub_request(self.sub_keys)))

    def _sub_request(self, keys: list[str]):
        req = geyser_pb2.SubscribeRequest()
        if keys:
            acc = geyser_pb2.SubscribeRequestFilterAccounts()
            acc.account.extend(keys)
            req.accounts["univ"].CopyFrom(acc)
        sl = geyser_pb2.SubscribeRequestFilterSlots()
        sl.filter_by_commitment = False
        sl.interslot_updates = True
        req.slots["s"].CopyFrom(sl)
        req.accounts["bank_sysvars"].account.append(bc.SLOT_HASHES)
        txf = geyser_pb2.SubscribeRequestFilterTransactions()
        txf.vote = False
        txf.failed = False
        txf.account_include.extend([txe.DLMM, txe.PUMP])
        req.transactions["dex"].CopyFrom(txf)
        req.commitment = geyser_pb2.PROCESSED
        return req

    def _pools_by_pk(self) -> dict[str, int]:
        return {rec.pubkey: rec.idx for rec in self.pools.values() if rec.pubkey}

    def _role(self, rec: PoolRec, pk: str) -> str | None:
        for row in self.acc_deps.get(pk) or []:
            if int(row.get("pool_idx")) == rec.idx:
                return row.get("role")
        return None

    def add_required(self, rec: PoolRec, pk: str, role: str) -> bool:
        if pk in rec.required:
            return False
        rec.required.add(pk)
        self.acc_deps.setdefault(pk, []).append({
            "pool_idx": rec.idx, "role": role, "kind": rec.kind, "required": True,
        })
        rec.status = ST_INCOMPLETE
        return pk not in self.bytes

    def invalidate(self, rec: PoolRec, rx_ns: int, slot: int) -> None:
        if rec.status != ST_STAGING:
            recon.invalidate(self.rf, self.proto_of[rec.idx], rec.idx, rx_ns, slot)
            if rec.last_s is not None:
                rec.s_before = dict(rec.last_s)
            rec.staged = []
        rec.status = ST_STAGING
        rec.upd_since = rx_ns
        rec.stage.setdefault("rx", rx_ns)
        rec.stage["slot"] = slot
        self._lat("lat_stage", _mono() - rx_ns)

    def publish_dlmm(self, rec: PoolRec, slot: int, rx_ns: int, accounts: dict) -> bool:
        pair = None
        bins = []
        for pk, role_l in ((k, [x["role"] for x in self.acc_deps.get(k) or [] if x["pool_idx"] == rec.idx])
                           for k in rec.required):
            row = accounts.get(pk)
            if not row or not row.get("data"):
                return False
            if sm.ROLE_DLMM_PAIR in role_l:
                pair = row["data"]
            elif sm.ROLE_DLMM_BIN in role_l:
                bins.append(row["data"])
        if pair is None:
            return False
        try:
            lb = d.parse_lbpair(pair)
        except Exception:
            self.m["decode_fail"] += 1
            return False
        need = dep.bin_keys_for_active(rec.pubkey, lb["active_id"])
        added = False
        for bpk in need:
            if self.add_required(rec, bpk, sm.ROLE_DLMM_BIN):
                added = True
        if added:
            self.subscribe_keys(list(self.acc_deps))
            self.fetch_async("dependency_result", [k for k in need if k not in self.bytes])
        if any(k not in accounts for k in need):
            rec.status = ST_INCOMPLETE
            return False
        snap = snap_dlmm(pair, [accounts[k]["data"] for k in need])
        if snap is None:
            rec.status = ST_INCOMPLETE
            return False
        rec.active_id = lb["active_id"]
        buf = io.BytesIO()
        live.write_dlmm(buf, snap)
        recon.auth(self.rf, live.PROTO_DLMM, rec.idx, slot, buf.getvalue())
        rec.status = ST_COHERENT
        rec.gen += 1
        published = {
            "kind": "dlmm",
            "active_id": lb["active_id"],
            "vol_acc": lb["vol_acc"],
            "vol_ref": lb["vol_ref"],
            "idx_ref": lb["idx_ref"],
            "last_upd": lb.get("last_upd"),
            "bin_step": lb["bin_step"],
            "base_factor": lb["base_factor"],
            "variable_fee_control": lb["variable_fee_control"],
            "reserve_x": snap["reserve_x"],
            "reserve_y": snap["reserve_y"],
            "bins": {b["id"]: (b["x"], b["y"]) for b in snap["bins"]},
            "slot": slot,
        }
        rec.last_s = published
        rec.last_blob = buf.getvalue()
        self.m["published"] += 1
        self._lat("lat_pub", _mono() - rx_ns)
        self._finish_publish(rec, published, blob=buf.getvalue(), proto=live.PROTO_DLMM)
        return True

    def publish_pump(self, rec: PoolRec, slot: int, rx_ns: int, accounts: dict) -> bool:
        pool_raw = vb = vq = glob = fee_raw = mint_raw = None
        for pk in rec.required:
            row = accounts.get(pk)
            if not row or not row.get("data"):
                return False
            roles = [x["role"] for x in self.acc_deps.get(pk) or [] if x["pool_idx"] == rec.idx]
            if sm.ROLE_PUMP_POOL in roles:
                pool_raw = row["data"]
            elif sm.ROLE_PUMP_VAULT_BASE in roles:
                vb = row["data"]
            elif sm.ROLE_PUMP_VAULT_QUOTE in roles:
                vq = row["data"]
            elif sm.ROLE_PUMP_GLOBAL in roles:
                glob = row["data"]
            elif sm.ROLE_PUMP_FEE_CONFIG in roles:
                fee_raw = row["data"]
            elif sm.ROLE_MINT in roles:
                mint_raw = row["data"]
        if pool_raw is None or vb is None or vq is None:
            rec.status = ST_INCOMPLETE
            return False
        p = live.parse_pump_pool(pool_raw)
        if not p:
            self.m["decode_fail"] += 1
            return False
        rb = d.token_amount(vb)
        rq = d.token_amount(vq)
        if rb == 0 or rq == 0:
            rec.status = ST_INCOMPLETE
            return False
        fees = live.parse_global(glob) if glob else self.fees
        self.fees = fees
        lp, proto, creator, disabled = fees
        virt = p.get("virtual_quote_reserves")
        if virt is None:
            rec.status = ST_INCOMPLETE
            return False
        pool_cr = int(p.get("creator_fee_bps") or 0)
        coin_cr = live.b58e(p["coin_creator"]) if p.get("coin_creator") else ""
        pool_creator = live.b58e(p["creator"]) if p.get("creator") else ""
        base_mint = live.b58e(p["base"]) if p.get("base") else ""
        quote_mint = live.b58e(p["quote"]) if p.get("quote") else ""
        supply = live.parse_mint_supply(mint_raw) if mint_raw else 0
        fee_st = None
        try:
            from pump_fee import parse_fee_config, parse_global_config, resolve_fee_state
            if fee_raw and glob:
                fc = parse_fee_config(fee_raw)
                gc = parse_global_config(glob)
                fee_st = resolve_fee_state(
                    fc, gc,
                    {
                        "creator": pool_creator, "coin_creator": coin_cr,
                        "creator_fee_bps": pool_cr, "base_mint": base_mint,
                        "quote_mint": quote_mint, "canonical": False,
                    },
                    supply, rb, rq, gate="coin_creator", noncanon="flat",
                )
                lp = int(fee_st["lp_fee_bps"])
                proto = int(fee_st["protocol_fee_bps"])
                creator = int(fee_st["creator_fee_bps"])
        except Exception:
            fee_st = None
        row = {
            "reserve_base": rb, "reserve_quote": rq,
            "virtual_quote": int(virt),
            "lp_fee_bps": lp, "protocol_fee_bps": proto,
            "creator_fee_bps": creator, "disabled": disabled,
            "status": 1 if (p.get("mayhem") or p.get("cashback")) else 0,
        }
        buf = io.BytesIO()
        live.write_pump(buf, row)
        recon.auth(self.rf, live.PROTO_PUMP, rec.idx, slot, buf.getvalue())
        rec.status = ST_COHERENT
        rec.gen += 1
        published = {
            "kind": "pump",
            "reserve_base": rb, "reserve_quote": rq,
            "virtual_quote": int(virt),
            "base_vault_amount": rb, "quote_vault_amount": rq,
            "virtual_quote_reserves": int(virt),
            "lp_fee_bps": lp, "protocol_fee_bps": proto,
            "creator_fee_bps": creator, "disabled": disabled,
            "slot": slot,
            "auth_version": "PUMP-AUTH-016",
            "pool_creator": pool_creator,
            "coin_creator": coin_cr,
            "pool_creator_fee_bps": pool_cr,
            "base_mint": base_mint,
            "quote_mint": quote_mint,
            "base_supply": supply,
            "fee_src": (fee_st or {}).get("fee_src"),
            "canonical": (fee_st or {}).get("canonical"),
            "market_cap": (fee_st or {}).get("market_cap"),
            "buyback_bps": (fee_st or {}).get("buyback_bps"),
        }
        rec.last_s = published
        rec.last_blob = buf.getvalue()
        self.m["published"] += 1
        self._lat("lat_pub", _mono() - rx_ns)
        self._finish_publish(rec, published, blob=buf.getvalue(), proto=live.PROTO_PUMP)
        return True

    def _finish_publish(self, rec: PoolRec, published: dict, blob: bytes, proto: int) -> None:
        stage = dict(rec.stage)
        staged = list(rec.staged)
        origin = "boot" if stage.get("sig") == b"boot" else "tx"
        sig = stage.get("sig")
        wv = 0
        for w in staged:
            try:
                wv = max(wv, int(w.get("write_version") or 0))
            except (TypeError, ValueError):
                pass
        flags = ap.COHERENT
        if rec.status == ST_GAPPED:
            flags |= ap.GAPPED
        self.auth.publish(
            rec.idx, slot=int(published.get("slot") or 0), blob=blob,
            proto=int(proto), sig=sig if isinstance(sig, (bytes, bytearray)) else None,
            txn_index=None,
            max_account_write_version=wv if staged else None,
            flags=flags, boot=(origin == "boot"),
        )
        rec.stage = {}
        rec.staged = []
        self.shadow.on_publish(
            idx=rec.idx, kind=rec.kind, pubkey=rec.pubkey,
            origin=origin, stage=stage, staged=staged,
            s_before=rec.s_before, s_pub=published,
        )

    def _fail_tx_incomplete(self, rec: PoolRec, sig: str, why: str) -> None:
        self.m["publish_incomplete_at_boundary"] += 1
        self.barrier.m["publish_incomplete_at_boundary"] += 1
        hx = sh.sig_hex(sig) if not isinstance(sig, str) else sig
        if hx:
            self.barrier.drop(hx, rec.idx)
        rec.stage = {}
        rec.staged = []
        rec.status = ST_INCOMPLETE
        recon.invalidate(self.rf, self.proto_of[rec.idx], rec.idx, _mono(), self.stream_slot)
        n = self.m["publish_incomplete_at_boundary"]
        if n <= 8 or n % 64 == 0:
            print(
                f"STATE-010  TX_INCOMPLETE n={n} idx={rec.idx} {why} "
                f"slot={self.stream_slot}",
                flush=True,
            )

    def try_publish(self, rec: PoolRec, stream_slot: int) -> None:
        if not self.pool_complete(rec):
            rec.status = ST_INCOMPLETE
            return
        st = rec.stage
        if not st:
            return
        sig = st.get("sig")
        wait = int(st.get("wait_slot") or (st.get("slot") or 0) + 1)
        if not sig:
            if stream_slot < wait:
                return
        elif sig != b"boot":
            hx = sh.sig_hex(sig)
            if not self.barrier.has_shape(hx, rec.idx):
                # Slot+1 is only for a known expected set. Shape can lag accounts.
                if stream_slot > int(st.get("slot") or 0) + 8:
                    # No classified exact swap joined this write. Liquidity /
                    # other ix — not STATE_TX_INCOMPLETE. Re-AUTH current bytes.
                    self.m["non_exact_reauth"] += 1
                    rec.stage["sig"] = b"boot"
                    rec.stage["reconcile"] = True
                    sig = b"boot"
                else:
                    self.m["publish_wait_shape"] += 1
                    self.barrier.m["publish_wait_shape"] += 1
                    return
            if sig != b"boot" and not self.barrier.can_commit(hx, rec.idx):
                missing = self.barrier.missing(hx, rec.idx)
                if stream_slot > int(st.get("slot") or 0):
                    self._fail_tx_incomplete(rec, hx or "", f"missing={len(missing)}")
                    return
                self.barrier.mark_wait(missing, lambda pk: self._role(rec, pk))
                self.m["publish_wait_pair"] = self.barrier.m["publish_wait_pair"]
                self.m["publish_wait_bin"] = self.barrier.m["publish_wait_bin"]
                self.m["publish_wait_vault"] = self.barrier.m["publish_wait_vault"]
                return
        if sig and sig != b"boot":
            reason, accounts = self.barrier.snapshot(sh.sig_hex(sig), rec.idx, rec.required, self.bytes)
            if accounts is None:
                rejected = self.m.setdefault("snapshot_rejections", {})
                rejected[reason] = rejected.get(reason, 0) + 1
                self._fail_tx_incomplete(rec, sh.sig_hex(sig), reason)
                return
        else:
            # Boot/reconciliation is still an uncertified predecessor. Freeze
            # its read set, without assigning it a transaction-write proof.
            accounts = {pk: dict(self.bytes.get(pk) or {}) for pk in rec.required}
        rx = int(st.get("rx") or _mono())
        slot = int(st.get("slot") or stream_slot)
        ok = False
        if rec.kind == "dlmm":
            ok = self.publish_dlmm(rec, slot, rx, accounts)
        else:
            ok = self.publish_pump(rec, slot, rx, accounts)
        if ok and sig and sig != b"boot":
            self.m["auth_predicted_exact"] += 1
            self.barrier.drop(sh.sig_hex(sig), rec.idx)
        elif ok and st.get("reconcile"):
            self.m["auth_reconciled_unknown"] += 1
        if not ok and rec.status == ST_STAGING:
            rec.status = ST_STAGING

    def apply_update(self, ev: dict, from_buf: bool = False) -> None:
        if ev.get("provider_generation") != self.provider_generation or self.provider_generation is None:
            self.m["stale_generation_events"] = self.m.get("stale_generation_events", 0) + 1
            return
        pk = ev["pubkey"]
        slot = ev["slot"]
        wv = ev["write_version"]
        floor = self.rpc_floors.get(pk, -1)
        if slot <= floor:
            if slot == floor and int((self.bytes.get(pk) or {}).get("slot") or 0) <= floor:
                # A write version cannot order a stream write against an RPC
                # snapshot. Require a later-slot update for this dependency.
                self.bytes.pop(pk, None)
                for dep_row in self.acc_deps.get(pk) or []:
                    rec = self.pools.get(int(dep_row["pool_idx"]))
                    if rec is not None:
                        self.invalidate(rec, ev["t_rx"], slot)
                        rec.stage.clear()
                        rec.staged.clear()
                self.m["rpc_same_slot_ambiguous"] = self.m.get("rpc_same_slot_ambiguous", 0) + 1
            return
        key = (pk, slot, wv)
        if key in self.seen:
            self.m["dup"] += 1
            return
        prev = self.last_wv.get(pk, -1)
        if 0 <= wv < prev:
            return
        self.seen.add(key)
        if len(self.seen) > 400000:
            self.seen.clear()
        self.last_wv[pk] = wv
        self.bytes[pk] = ev
        deps = self.acc_deps.get(pk) or []
        if not deps:
            return
        if self.bootstrapping and not from_buf:
            return
        for dep_row in deps:
            rec = self.pools.get(int(dep_row["pool_idx"]))
            if rec is None:
                continue
            self.invalidate(rec, ev["t_rx"], slot)
            st = rec.stage
            rec.staged.append({
                "pubkey": pk,
                "role": dep_row.get("role"),
                "slot": slot,
                "write_version": wv,
                "txn_sig": sh.sig_hex(ev.get("txn_sig")),
                "dlen": ev.get("dlen"),
            })
            hx = sh.sig_hex(ev.get("txn_sig"))
            if hx:
                self.barrier.note_write(hx, slot, rec.idx, pk, version=ev)
            if ev.get("txn_sig") and st.get("sig") and ev["txn_sig"] != st["sig"] and ev["slot"] == st.get("slot"):
                st["wait_slot"] = slot + 1
            elif ev.get("txn_sig"):
                st["sig"] = ev["txn_sig"]
                st["slot"] = slot
            else:
                st["wait_slot"] = slot + 1
                st["slot"] = slot

    def apply_tx(self, ev: dict) -> None:
        if ev.get("provider_generation") != self.provider_generation or self.provider_generation is None:
            return
        parsed = ev.get("parsed")
        if not parsed:
            return
        sig = parsed.get("sig")
        slot = int(ev.get("slot") or 0)
        expect = txe.expect_from_instructions(
            parsed.get("keys") or [],
            parsed.get("instructions") or [],
            self.acc_deps,
            self._pools_by_pk(),
        )
        klass = txe.tx_exact_status(parsed.get("instructions") or [])
        if klass["n_unknown"]:
            self.m["tx_unknown_dex"] += 1
            self.m["unsupported_shape"] += 1
        if klass["n_exact"]:
            self.m["tx_exact_seen"] += klass["n_exact"]
        if not expect:
            return
        for idx, spec in expect.items():
            rec = self.pools.get(int(idx))
            if rec is None:
                continue
            for pk in spec["expected"]:
                role = self._role(rec, pk)
                if role is None and rec.kind == "dlmm" and pk != rec.pubkey:
                    if self.add_required(rec, pk, sm.ROLE_DLMM_BIN):
                        self.subscribe_keys(list(self.acc_deps))
        self.barrier.note_tx(sig, slot, expect)
        if klass["n_exact"]:
            self._fastsoak_predict(sig, slot, expect, parsed)
        self.maybe_publish(self.stream_slot)

    def _fastsoak_predict(self, sig: str, slot: int, expect: dict, parsed: dict) -> None:
        ixs = parsed.get("instructions") or []
        for idx, spec in expect.items():
            rec = self.pools.get(int(idx))
            if rec is None:
                continue
            if rec.last_s is None or rec.last_blob is None:
                self.m["fastsoak_skip_no_auth"] += 1
                continue
            if rec.kind == "pump":
                cpis = ov.cpis_from_parsed(ixs, rec.pubkey)
                if any(c.get("kind") == "unknown" for c in cpis):
                    self.m["fastsoak_fail_closed"] += 1
                    continue
                if not cpis:
                    self.m["fastsoak_skip_apply"] += 1
                    continue
                term, fail = ov.apply_parsed(rec.last_s, cpis)
                if fail or not term:
                    self.m["fastsoak_fail_closed" if fail == "unsupported_cpi" else "fastsoak_skip_apply"] += 1
                    continue
                self.m["fastsoak_predict"] += 1
                last = cpis[-1]
                self.shadow.ingest_direct({
                    "sig_hex": sig,
                    "pool": rec.pubkey,
                    "n": {
                        "pool_idx": rec.idx,
                        "direction": last.get("direction"),
                        "amount_in": last.get("amount"),
                        "cpis": cpis,
                        "model": "pump-overlay-016",
                    },
                    "s_prime": term,
                    "auth_slot": rec.last_s.get("slot"),
                    "tx_exact": 1,
                    "source": "fastsoak",
                })
                continue
            hit = None
            for ix in ixs:
                v = txe.classify_ix(ix.get("program") or "", ix.get("data") or b"")
                if v is None:
                    continue
                accs = ix.get("accounts") or []
                if accs and accs[0] == spec.get("pubkey"):
                    hit = ix
                    break
            if hit is None:
                self.m["fastsoak_skip_apply"] += 1
                continue
            data = hit.get("data") or b""
            if isinstance(data, str):
                self.m["fastsoak_skip_apply"] += 1
                continue
            sp = an.apply_ix(rec.last_s, list(hit.get("accounts") or []), data, blob=rec.last_blob)
            if not sp:
                self.m["fastsoak_skip_apply"] += 1
                continue
            self.m["fastsoak_predict"] += 1
            self.shadow.ingest_direct({
                "sig_hex": sig,
                "pool": rec.pubkey,
                "n": {
                    "pool_idx": rec.idx,
                    "direction": sp.get("direction"),
                    "amount_in": sp.get("amount_in"),
                },
                "s_prime": sp,
                "auth_slot": rec.last_s.get("slot"),
                "tx_exact": 1,
                "source": "fastsoak",
            })

    def maybe_publish(self, stream_slot: int) -> None:
        for rec in self.pools.values():
            if rec.status in (ST_STAGING, ST_INCOMPLETE, ST_GAPPED):
                self.try_publish(rec, stream_slot)

    def fetch_async(self, kind: str, keys: list[str], token: str | None = None) -> None:
        generation = self.provider_generation
        def fetch():
            try:
                accounts = dep._chunk_get(keys)
                self.q.put({"kind": kind, "provider_generation": generation,
                            "token": token, "accounts": accounts})
            except Exception as ex:
                self.q.put({"kind": "fetch_error", "provider_generation": generation,
                            "token": token, "error": type(ex).__name__})
        threading.Thread(target=fetch, name="s008-fetch", daemon=True).start()

    def bootstrap(self, generation: str, token: str) -> None:
        # Worker only derives/fetches. It never mutates publication state.
        try:
            univ = sm.load_univ()
            gen = dep.derive_generation(univ)
            self.q.put({"kind": "bootstrap_plan", "provider_generation": generation,
                        "token": token, "plan": gen})
        except Exception as ex:
            self.q.put({"kind": "fetch_error", "provider_generation": generation,
                        "token": token, "error": type(ex).__name__})

    def finish_bootstrap(self, ev: dict) -> None:
        if (self.provider_generation is None or ev.get("provider_generation") != self.provider_generation
                or self.bootstrap_token is None or ev.get("token") != self.bootstrap_token or self.bootstrap_done):
            return
        accounts = ev["accounts"]
        self.bytes = {pk: self.rpc_row(pk, row) for pk, row in accounts.items()
                      if row.get("data") and int(row.get("slot") or 0) > 0}
        self.rpc_floors = {pk: int(row["slot"]) for pk, row in self.bytes.items()}
        self.bootstrap_slot = max(self.rpc_floors.values(), default=0)
        # Preserve receipt order and each account's own RPC floor. A maximum
        # across RPC batches must not discard valid writes to an earlier batch.
        buffered, self.buf = self.buf, []
        for row in buffered:
            if row["kind"] == "account":
                self.apply_update(row, from_buf=True)
            else:
                self.apply_tx(row)
        self.bootstrap_done = True
        self.bootstrapping = False
        for rec in self.pools.values():
            if self.pool_complete(rec):
                slot = max(int(self.bytes[pk].get("slot") or 0) for pk in rec.required)
                rec.stage = {"slot": slot, "rx": _mono(), "sig": b"boot"}
                self.try_publish(rec, max(self.stream_slot, slot))
            else:
                rec.status = ST_INCOMPLETE
        self._recount()
        if self.stream_slot >= self.bootstrap_slot > 0:
            self.mark_ready()
        self._pools_json()

    def univ_loop(self) -> None:
        while not self.stop.wait(UNIV_POLL_S):
            with self.lock:
                generation = self.provider_generation
                if generation is None or self.bootstrapping:
                    continue
                prior_mtime, prior_n = self.univ_mtime, self.univ_n
                known = set(self.bytes)
            try:
                if not UNIV.exists():
                    continue
                mt = UNIV.stat().st_mtime
                univ = sm.load_univ()
                n = int(univ.get("n") or len(univ.get("pools") or []))
                if mt == prior_mtime and n == prior_n:
                    continue
                gen = dep.derive_generation(univ)
                extra = dep._chunk_get([k for k in gen["accounts"] if k not in known])
                self.q.put({"kind": "univ_result", "provider_generation": generation,
                            "plan": gen, "accounts": extra, "mtime": mt})
            except Exception as ex:
                self.q.put({"kind": "fetch_error", "provider_generation": generation,
                            "token": None, "error": type(ex).__name__})

    def shadow_loop(self) -> None:
        path = PAPER_AUDIT
        while not path.exists() and not self.stop.is_set():
            time.sleep(1)
        if self.stop.is_set():
            return
        with path.open("r", encoding="utf-8") as f:
            f.seek(0, 2)
            while not self.stop.is_set():
                line = f.readline()
                if not line:
                    time.sleep(0.05)
                    f.seek(f.tell())
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                with self.lock:
                    if self.ready:
                        self.shadow.ingest_paper(rec)

    def metrics_loop(self) -> None:
        hb = Path("/dev/shm/arb_state008_health.json")
        while not self.stop.is_set():
            time.sleep(5)
            with self.lock:
                self._recount()
                self.shadow.expire_stale()
                rates = self.shadow.rates()
                payload = {
                    "ready": self.ready,
                    "univ_n": self.univ_n,
                    "dependencies_expected": self.m["dependencies_expected"],
                    "dependencies_subscribed": self.m["dependencies_subscribed"],
                    "dependencies_received": self.m["dependencies_received"],
                    "pool_complete": self.m["pool_complete"],
                    "n_pool": len(self.pools),
                    "updates": self.m["updates"],
                    "published": self.m["published"],
                    "gap_count": self.m["gaps"],
                    "state_mismatch_count": rates["shadow_mismatch"],
                    "exact": rates["shadow_exact"],
                    "shadow": rates,
                    "reconnects": self.m["reconnects"],
                    "staging_latency": {
                        k: _pct(self.m["lat_stage"], p)
                        for k, p in (("p50", 0.5), ("p90", 0.9), ("p99", 0.99))
                    },
                    "coherent_publish_latency": {
                        k: _pct(self.m["lat_pub"], p)
                        for k, p in (("p50", 0.5), ("p90", 0.9), ("p99", 0.99))
                    },
                    "stream_slot": self.stream_slot,
                    "bootstrap_slot": self.bootstrap_slot,
                    "provider_generation": self.provider_generation,
                    "bootstrap_done": self.bootstrap_done,
                    "stale_generation_events": self.m.get("stale_generation_events", 0),
                    "stale_bootstrap_results": self.m.get("stale_bootstrap_results", 0),
                    "rpc_same_slot_ambiguous": self.m.get("rpc_same_slot_ambiguous", 0),
                    "bootstrap_buffer_overflow": self.m.get("bootstrap_buffer_overflow", 0),
                    "fetch_errors": self.m.get("fetch_errors", 0),
                    "publish_wait_pair": self.m["publish_wait_pair"],
                    "publish_wait_bin": self.m["publish_wait_bin"],
                    "publish_wait_vault": self.m["publish_wait_vault"],
                    "publish_incomplete_at_boundary": self.m["publish_incomplete_at_boundary"],
                    "non_exact_reauth": self.m["non_exact_reauth"],
                    "auth_predicted_exact": self.m["auth_predicted_exact"],
                    "auth_reconciled_unknown": self.m["auth_reconciled_unknown"],
                    "unsupported_shape": self.m["unsupported_shape"],
                    "tx_shape": self.barrier.m["tx_shape"],
                    "barrier_evicted_transactions": self.barrier.m["evicted_transactions"],
                    "snapshot_rejections": dict(self.m.get("snapshot_rejections", {})),
                    "tx_rx": self.m["tx_rx"],
                    "tx_exact_seen": self.m["tx_exact_seen"],
                    "tx_unknown_dex": self.m["tx_unknown_dex"],
                    "fastsoak_predict": self.m["fastsoak_predict"],
                    "fastsoak_skip_no_auth": self.m["fastsoak_skip_no_auth"],
                    "fastsoak_skip_apply": self.m["fastsoak_skip_apply"],
                    "status": {ST_NAME[i]: sum(1 for r in self.pools.values() if r.status == i)
                               for i in range(4)},
                }
            # Heartbeat on tmpfs so ENOSPC on / cannot look like a live worker.
            try:
                hb.write_text(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "pid": os.getpid(),
                    "ready": self.ready,
                    "updates": self.m["updates"],
                    "published": self.m["published"],
                    "stream_slot": self.stream_slot,
                    "tx_rx": self.m["tx_rx"],
                    "fastsoak_predict": self.m["fastsoak_predict"],
                    "metrics_ok": True,
                }) + "\n", encoding="utf-8")
            except OSError:
                pass
            try:
                tmp = METRICS.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                tmp.replace(METRICS)
            except OSError as e:
                try:
                    hb.write_text(json.dumps({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "pid": os.getpid(),
                        "ready": self.ready,
                        "updates": self.m["updates"],
                        "published": self.m["published"],
                        "stream_slot": self.stream_slot,
                        "tx_rx": self.m["tx_rx"],
                        "fastsoak_predict": self.m["fastsoak_predict"],
                        "metrics_ok": False,
                        "metrics_error": str(e),
                    }) + "\n", encoding="utf-8")
                except OSError:
                    pass
            print(
                f"STATE-008  up ready={int(self.ready)} "
                f"exp={self.m['dependencies_expected']} "
                f"sub={self.m['dependencies_subscribed']} "
                f"rx={self.m['dependencies_received']} "
                f"complete={self.m['pool_complete']}/{len(self.pools)} "
                f"pub={self.m['published']} gaps={self.m['gaps']} "
                f"shadow={rates['shadow_exact']}/{rates['shadow_total']} "
                f"mis={rates['shadow_mismatch']} slot={self.stream_slot} "
                f"txe={rates.get('tx_exact_bitexact')}/{rates.get('tx_exact_shadowed')} "
                f"wait_bin={self.m['publish_wait_bin']} "
                f"incomp={self.m['publish_incomplete_at_boundary']} "
                f"reauth={self.m['non_exact_reauth']} "
                f"txe_seen={self.m['tx_exact_seen']} fs={self.m['fastsoak_predict']}",
                flush=True,
            )

    def handle_event(self, ev: dict) -> str:
        """Single state owner; decode_loop holds the connection lock."""
        generation = ev.get("provider_generation", ev.get("generation"))
        if generation is None or generation != self.provider_generation:
            self.m["stale_generation_events"] = self.m.get("stale_generation_events", 0) + 1
            return "stale_generation"
        kind = ev["kind"]
        if kind.startswith("bank_"):
            result = self.bank_journal.apply(ev)
            if kind != "bank_slot" or ev["status"] != 0:
                return result
        if kind == "bank_slot":
            prev = self.stream_slot
            self.stream_slot = max(prev, ev["slot"])
            if prev and ev["slot"] > prev + 32:
                self.reset_connection(generation, f"slot_gap {prev}->{ev['slot']}")
                self.stream_slot = ev["slot"]
            if self.bootstrapping and self.bootstrap_token is None:
                self.bootstrap_token = uuid.uuid4().hex
                threading.Thread(target=self.bootstrap,
                                 args=(generation, self.bootstrap_token),
                                 name="s008-boot", daemon=True).start()
            if self.bootstrap_done and not self.ready and self.stream_slot >= self.bootstrap_slot > 0:
                self.mark_ready()
            if self.ready:
                for sig, idx in self.barrier.expire_at_boundary(self.stream_slot):
                    rec = self.pools.get(idx)
                    if rec is not None and rec.status == ST_STAGING:
                        self._fail_tx_incomplete(rec, sig, "slot_boundary")
                self.maybe_publish(self.stream_slot)
            return "processed_slot"
        if kind in ("bootstrap_plan", "bootstrap_result"):
            if self.bootstrap_token is None or ev.get("token") != self.bootstrap_token or self.bootstrap_done:
                self.m["stale_bootstrap_results"] = self.m.get("stale_bootstrap_results", 0) + 1
                return "stale_bootstrap"
            if kind == "bootstrap_plan":
                self.install_generation(ev["plan"])
                self.subscribe_keys(list(self.acc_deps))
                self.fetch_async("bootstrap_result", list(self.acc_deps), self.bootstrap_token)
            else:
                self.finish_bootstrap(ev)
            return kind
        if kind == "fetch_error":
            self.m["fetch_errors"] = self.m.get("fetch_errors", 0) + 1
            if ev.get("token") is not None and ev["token"] == self.bootstrap_token and not self.bootstrap_done:
                self.bootstrap_token = None  # Retry on the next processed slot.
            return "fetch_error"
        if kind in ("univ_result", "dependency_result"):
            if self.bootstrapping:
                return "bootstrap_in_progress"
            if kind == "univ_result":
                self.univ_mtime = ev["mtime"]
                self.install_generation(ev["plan"], ev["accounts"])
                self.subscribe_keys(list(self.acc_deps))
            else:
                for pk, row in ev["accounts"].items():
                    if pk not in self.bytes:
                        self.bytes[pk] = self.rpc_row(pk, row)
                        self.rpc_floors[pk] = int(row.get("slot") or 0)
            self._recount()
            self.maybe_publish(self.stream_slot)
            return kind
        if kind in ("tx", "account"):
            if self.bootstrapping:
                self.buf.append(ev)
                if len(self.buf) > 20000:
                    self.m["bootstrap_buffer_overflow"] = self.m.get("bootstrap_buffer_overflow", 0) + 1
                    self.reset_connection(generation, "bootstrap_buffer_overflow")
                    return "bootstrap_buffer_overflow"
                return "buffered"
            if kind == "tx":
                self.apply_tx(ev)
            else:
                self.apply_update(ev)
                self.maybe_publish(self.stream_slot)
            return kind
        return "ignored"

    def decode_loop(self) -> None:
        with (CAP / "bank_context.jsonl").open("a", encoding="utf-8", buffering=1) as bank_log:
            while not self.stop.is_set():
                try:
                    ev = self.q.get(timeout=0.05)
                except queue.Empty:
                    with self.lock:
                        if self.ready:
                            self.maybe_publish(self.stream_slot)
                    continue
                with self.lock:
                    result = self.handle_event(ev)
                if ev.get("kind", "").startswith("bank_"):
                    bank_log.write(json.dumps(dict(ev, journal_result=result), separators=(",", ":")) + "\n")

    def grpc_loop(self) -> None:
        if geyser_pb2 is None:
            raise RuntimeError("geyser proto not generated")
        token = config.x_token()
        if not token:
            raise RuntimeError("SHYFT_X_TOKEN missing")
        host = config.grpc_url()
        creds = grpc.ssl_channel_credentials()
        opts = (
            ("grpc.max_receive_message_length", 1024 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 10_000),
            ("grpc.keepalive_timeout_ms", 5_000),
            ("grpc.http2.min_time_between_pings_ms", 10_000),
        )
        def req_iter(generation, requests):
            # First request is empty accounts; bootstrap replaces it.
            yield self._sub_request([])
            while not self.stop.is_set() and self.provider_generation == generation:
                try:
                    item_generation, request = requests.get(timeout=1.0)
                    if item_generation == generation:
                        yield request
                except queue.Empty:
                    ping = geyser_pb2.SubscribeRequest()
                    ping.ping.id = 1
                    yield ping

        while not self.stop.is_set():
            generation = uuid.uuid4().hex
            with self.lock:
                self.reset_connection(generation, "grpc_connect")
            self.q.put({"kind": "bank_generation", "generation": generation, "rx": _mono()})
            channel = None
            try:
                channel = grpc.secure_channel(host, creds, options=opts)
                stub = geyser_pb2_grpc.GeyserStub(channel)
                print(f"STATE-008  connect host={host.split(':')[0]} region={config.region()}", flush=True)
                for upd in stub.Subscribe(req_iter(generation, self.req_q), metadata=(("x-token", token),)):
                    t_rx = _mono()
                    if upd.HasField("ping"):
                        pong = geyser_pb2.SubscribeRequest()
                        pong.ping.id = 1
                        self.req_q.put((generation, pong))
                        continue
                    if upd.HasField("pong"):
                        continue
                    if upd.HasField("slot"):
                        self.q.put({"kind": "bank_slot", "slot": int(upd.slot.slot), "t_rx": t_rx,
                                    "rx": t_rx, "generation": generation,
                                    "bank_id": bc.optional_field(upd.slot, "bank_id"),
                                    "parent": bc.optional_field(upd.slot, "parent"),
                                    "status": int(upd.slot.status)})
                        continue
                    if upd.HasField("account"):
                        info = upd.account.account
                        pk = _b58(info.pubkey)
                        if pk == bc.SLOT_HASHES:
                            self.q.put({"kind": "bank_account", "slot": int(upd.account.slot),
                                        "generation": generation, "rx": t_rx,
                                        "bank_id": bc.optional_field(upd.account, "bank_id"),
                                        "startup": bool(upd.account.is_startup), "owner": _b58(info.owner),
                                        "write_version": int(info.write_version), "data_hex": bytes(info.data).hex()})
                            continue
                        self.m["updates"] += 1
                        self.q.put({
                            "kind": "account", "t_rx": t_rx, "utc": _utc(),
                            "provider_generation": generation,
                            "bank_id": bc.optional_field(upd.account, "bank_id"),
                            "slot": int(upd.account.slot),
                            "write_version": int(info.write_version),
                            "pubkey": pk, "owner": _b58(info.owner),
                            "lamports": int(info.lamports),
                            "dlen": len(info.data), "data": bytes(info.data),
                            "txn_sig": bytes(info.txn_signature) if info.txn_signature else None,
                        })
                    if upd.HasField("transaction"):
                        info = upd.transaction.transaction
                        if getattr(info, "is_vote", False):
                            continue
                        parsed = txe.parse_geyser_tx(info, _b58)
                        self.m["tx_rx"] += 1
                        if parsed is None:
                            continue
                        self.q.put({
                            "kind": "tx",
                            "provider_generation": generation,
                            "bank_id": bc.optional_field(upd.transaction, "bank_id"),
                            "txn_index": int(info.index),
                            "t_rx": t_rx,
                            "slot": int(upd.transaction.slot),
                            "parsed": parsed,
                        })
            except grpc.RpcError as ex:
                self.m["reconnects"] += 1
                code = ex.code().name if hasattr(ex, "code") else "RPC"
                print(f"STATE-008  grpc {code}", flush=True)
            except Exception as ex:
                self.m["reconnects"] += 1
                print(f"STATE-008  grpc {type(ex).__name__}", flush=True)
            finally:
                with self.lock:
                    if self.provider_generation == generation:
                        self.reset_connection(None, "grpc_disconnect")
                self.q.put({"kind": "bank_disconnect", "generation": generation, "rx": _mono()})
                if channel is not None:
                    channel.close()
            self.stop.wait(1.5)

    def run(self) -> int:
        config.load_env()
        live.load_dotenv()
        print("STATE-008  Shyft Yellowstone FRA  FUNDED=0  complete-deps", flush=True)
        threading.Thread(target=self.decode_loop, name="s008-decode", daemon=True).start()
        threading.Thread(target=self.metrics_loop, name="s008-metrics", daemon=True).start()
        threading.Thread(target=self.univ_loop, name="s008-univ", daemon=True).start()
        threading.Thread(target=self.shadow_loop, name="s008-shadow", daemon=True).start()
        try:
            self.grpc_loop()
        except KeyboardInterrupt:
            self.stop.set()
        return 0


def main() -> int:
    return State008().run()


if __name__ == "__main__":
    raise SystemExit(main())
