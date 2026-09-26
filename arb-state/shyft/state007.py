#!/usr/bin/env python3
"""STATE-007 — Shyft Frankfurt Yellowstone → canonical pool S.

Search never calls this process. FUNDED stays 0.

Bootstrap algorithm (no unseen gap):
  1. Open Yellowstone Subscribe (accounts + slots), PROCESSED.
  2. Buffer every account update. Wait until stream_slot > 0.
  3. RPC getMultipleAccounts (processed) for the subscribed set.
     bootstrap_slot := RPC context.slot.
  4. Replay buffered updates with (slot, write_version) newer than bootstrap.
  5. STATE_READY only if the stream stayed up and stream_slot >= bootstrap_slot.
  Otherwise STATE_NOT_READY / SEND BLOCKED.

Coherency algorithm (correctness > availability):
  If account.txn_signature is present, stage by (slot, txn_sig).
  Else conservative slot staging: first relevant write → UPDATING;
  publish only after a later slot arrives (all same-slot writes assumed in).
  Missing required BinArray after LbPair active_id move → stay UPDATING.
"""
from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

import grpc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gen"))
sys.path.insert(0, str(HERE.resolve().parents[1].parent / "arb-cap"))
sys.path.insert(0, str(Path("/home/louis/arb-cap")))

import config  # noqa: E402
import recon  # noqa: E402
import submap as sm  # noqa: E402
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

try:
    import geyser_pb2
    import geyser_pb2_grpc
except ImportError:  # generated at deploy
    geyser_pb2 = None  # type: ignore
    geyser_pb2_grpc = None  # type: ignore

CAP = Path("/home/louis/captures/state007")
RECON_PATH = Path("/home/louis/captures/paper_orbit/recon.bin")
READY = CAP / "READY"
PLANE = CAP / "PLANE.json"
METRICS = CAP / "METRICS.json"
JOURNAL = CAP / "updates.jsonl"
COMPARE = CAP / "COMPARE.json"
HURDLE = 525_000
COMPARE_S = 20.0
UNIV_POLL_S = 15.0
LAT_CAP = 8192


def _mono() -> int:
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _b58(raw: bytes) -> str:
    return d._pk(raw) if raw else ""


class Metrics:
    def __init__(self) -> None:
        self.updates = 0
        self.unique: set[str] = set()
        self.pools_mutated: set[int] = set()
        self.published = 0
        self.updating = 0
        self.updating_max = 0
        self.reconnects = 0
        self.gaps = 0
        self.decode_fail = 0
        self.dup = 0
        self.ooo = 0
        self.stale_wv = 0
        self.suppressed = 0
        self.mismatch = 0
        self.rpc_lag = 0
        self.exact = 0
        self.lat_dec: list[int] = []
        self.lat_upd: list[int] = []
        self.lat_pub: list[int] = []
        self.lat_sync: list[int] = []
        self.stream_slot = 0
        self.bootstrap_slot = 0
        self.ready = False
        self.lock = threading.Lock()

    def add_lat(self, bucket: list[int], ns: int) -> None:
        if ns < 0:
            return
        bucket.append(ns)
        if len(bucket) > LAT_CAP:
            del bucket[: len(bucket) - LAT_CAP]


def _pct(v: list[int], p: float) -> int:
    if not v:
        return 0
    s = sorted(v)
    i = int(p * (len(s) - 1))
    return s[i]


def snap_from_accounts(pair_data: bytes, bin_datas: list[bytes]) -> dict | None:
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


class Plane:
    def __init__(self) -> None:
        self.sub = sm.build_submap()
        self.bytes: dict[str, dict] = {}
        self.pool_acc: dict[int, dict[str, str]] = defaultdict(dict)
        self.stage: dict[int, dict] = {}
        self.updating: set[int] = set()
        self.upd_since: dict[int, int] = {}
        self.gen: dict[int, int] = defaultdict(int)
        self.last_wv: dict[str, int] = {}
        self.seen: set[tuple[str, int, int]] = set()
        self.ready = False
        self.uncertain = True
        self.stream_slot = 0
        self.bootstrap_slot = 0
        self.buf: list[dict] = []
        self.bootstrapping = True
        self.proto_of: dict[int, int] = {}
        univ_pools = {int(x.get("idx") or -1): x for x in sm.load_univ().get("pools") or []}
        for p in self.sub["pools"]:
            self.proto_of[p["idx"]] = live.PROTO_DLMM if p["kind"] == "dlmm" else live.PROTO_PUMP
            meta = univ_pools.get(p["idx"]) or {"pubkey": p.get("pubkey"), "proto": p["kind"]}
            for pk, role in sm.accounts_for_pool(meta):
                self.pool_acc[p["idx"]][pk] = role

    def keys(self) -> list[str]:
        return list(self.sub["accounts"])


class State007:
    def __init__(self) -> None:
        self.m = Metrics()
        self.q: queue.SimpleQueue = queue.SimpleQueue()
        self.j: queue.SimpleQueue = queue.SimpleQueue()
        self.req_q: queue.SimpleQueue = queue.SimpleQueue()
        self.plane = Plane()
        self.rf = recon.open_recon(RECON_PATH)
        self.stop = threading.Event()
        self.fees = (20, 5, 0, 0)
        CAP.mkdir(parents=True, exist_ok=True)

    def mark_uncertain(self, why: str) -> None:
        self.plane.ready = False
        self.plane.uncertain = True
        self.m.ready = False
        self.m.gaps += 1
        if READY.exists():
            READY.unlink()
        recon.plane(self.rf, False, self.plane.stream_slot)
        self._plane_json(why)
        print(f"STATE-007  UNCERTAIN  {why}", flush=True)

    def mark_ready(self) -> None:
        self.plane.ready = True
        self.plane.uncertain = False
        self.plane.bootstrapping = False
        self.m.ready = True
        READY.write_text("1\n", encoding="utf-8")
        recon.plane(self.rf, True, self.plane.stream_slot)
        self._plane_json("ready")
        print(
            f"STATE-007  READY  stream_slot={self.plane.stream_slot} "
            f"bootstrap_slot={self.plane.bootstrap_slot} "
            f"accounts={len(self.plane.keys())} pools={self.plane.sub['n_pool']}",
            flush=True,
        )

    def _plane_json(self, why: str) -> None:
        PLANE.write_text(
            json.dumps(
                {
                    "ready": self.plane.ready,
                    "why": why,
                    "region": config.region(),
                    "endpoint_host": config.grpc_url().split(":")[0],
                    "n_account": len(self.plane.keys()),
                    "n_pool": self.plane.sub["n_pool"],
                    "stream_slot": self.plane.stream_slot,
                    "bootstrap_slot": self.plane.bootstrap_slot,
                    "updating": sorted(self.plane.updating),
                    "ts": _utc(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def invalidate(self, idx: int, rx_ns: int, slot: int) -> None:
        if idx not in self.plane.updating:
            recon.invalidate(self.rf, self.plane.proto_of.get(idx, live.PROTO_DLMM), idx, rx_ns, slot)
            self.plane.updating.add(idx)
            self.plane.upd_since[idx] = rx_ns
            self.m.updating = len(self.plane.updating)
            self.m.updating_max = max(self.m.updating_max, self.m.updating)
            self.m.add_lat(self.m.lat_upd, _mono() - rx_ns)

    def publish_dlmm(self, idx: int, slot: int, rx_ns: int) -> bool:
        roles = self.plane.pool_acc.get(idx) or {}
        pair = None
        bins = []
        for pk, role in roles.items():
            row = self.plane.bytes.get(pk)
            if not row or not row.get("data"):
                continue
            if role == sm.ROLE_DLMM_PAIR:
                pair = row["data"]
            elif role == sm.ROLE_DLMM_BIN:
                bins.append(row["data"])
        if pair is None:
            return False
        try:
            lb = d.parse_lbpair(pair)
        except Exception:
            self.m.decode_fail += 1
            return False
        need = [d.bin_array_pda(next(k for k, r in roles.items() if r == sm.ROLE_DLMM_PAIR), i)
                for i in d.array_indexes(lb["active_id"])]
        have = {pk for pk, r in roles.items() if r == sm.ROLE_DLMM_BIN and pk in self.plane.bytes}
        # Subscribe any newly required bin arrays (active_id moved).
        missing = [k for k in need if k not in have and k not in self.plane.bytes]
        if missing:
            return False
        snap = snap_from_accounts(pair, [self.plane.bytes[k]["data"] for k in need if k in self.plane.bytes])
        if snap is None:
            return False
        buf = io.BytesIO()
        live.write_dlmm(buf, snap)
        recon.auth(self.rf, live.PROTO_DLMM, idx, slot, buf.getvalue())
        self.plane.updating.discard(idx)
        self.plane.gen[idx] += 1
        self.m.published += 1
        self.m.updating = len(self.plane.updating)
        self.m.add_lat(self.m.lat_pub, _mono() - rx_ns)
        if idx in self.plane.upd_since:
            self.m.add_lat(self.m.lat_sync, _mono() - self.plane.upd_since.pop(idx))
        return True

    def publish_pump(self, idx: int, slot: int, rx_ns: int) -> bool:
        roles = self.plane.pool_acc.get(idx) or {}
        pool_raw = None
        vb = vq = None
        for pk, role in roles.items():
            row = self.plane.bytes.get(pk)
            if not row or not row.get("data"):
                continue
            if role == sm.ROLE_PUMP_POOL:
                pool_raw = row["data"]
            elif role == sm.ROLE_PUMP_VAULT_BASE:
                vb = row["data"]
            elif role == sm.ROLE_PUMP_VAULT_QUOTE:
                vq = row["data"]
        if pool_raw is None or vb is None or vq is None:
            return False
        p = live.parse_pump_pool(pool_raw)
        if not p:
            self.m.decode_fail += 1
            return False
        rb = d.token_amount(vb)
        rq = d.token_amount(vq)
        if rb == 0 or rq == 0:
            return False
        lp, proto, creator, disabled = self.fees
        row = {
            "reserve_base": rb,
            "reserve_quote": rq,
            "virtual_quote": 0,
            "lp_fee_bps": lp,
            "protocol_fee_bps": proto,
            "creator_fee_bps": creator,
            "disabled": disabled,
            "status": 1 if p.get("mayhem") else 0,
        }
        buf = io.BytesIO()
        live.write_pump(buf, row)
        recon.auth(self.rf, live.PROTO_PUMP, idx, slot, buf.getvalue())
        self.plane.updating.discard(idx)
        self.plane.gen[idx] += 1
        self.m.published += 1
        self.m.updating = len(self.plane.updating)
        self.m.add_lat(self.m.lat_pub, _mono() - rx_ns)
        if idx in self.plane.upd_since:
            self.m.add_lat(self.m.lat_sync, _mono() - self.plane.upd_since.pop(idx))
        return True

    def apply_update(self, ev: dict, from_buf: bool = False) -> None:
        pk = ev["pubkey"]
        slot = ev["slot"]
        wv = ev["write_version"]
        rx = ev["t_rx"]
        key = (pk, slot, wv)
        if key in self.plane.seen:
            self.m.dup += 1
            return
        prev = self.plane.last_wv.get(pk, -1)
        if 0 <= wv < prev:
            self.m.stale_wv += 1
            return
        if prev >= 0 and wv < prev:
            self.m.ooo += 1
        self.plane.seen.add(key)
        if len(self.plane.seen) > 200000:
            self.plane.seen.clear()
        self.plane.last_wv[pk] = wv
        self.plane.bytes[pk] = ev
        deps = self.plane.sub["accounts"].get(pk) or []
        if not deps:
            return
        self.m.add_lat(self.m.lat_dec, _mono() - rx)
        for dep in deps:
            idx = int(dep["pool_idx"])
            self.m.pools_mutated.add(idx)
            if self.plane.bootstrapping and not from_buf:
                continue
            self.invalidate(idx, rx, slot)
            st = self.plane.stage.setdefault(idx, {"slot": slot, "sig": ev.get("txn_sig"), "rx": rx})
            if ev.get("txn_sig") and st.get("sig") and ev["txn_sig"] != st["sig"] and ev["slot"] == st["slot"]:
                # another tx in same slot — stay UPDATING until later slot
                st["wait_slot"] = slot + 1
            elif ev.get("txn_sig"):
                st["sig"] = ev["txn_sig"]
                st["slot"] = slot
            else:
                st["wait_slot"] = slot + 1
                st["slot"] = slot

    def maybe_publish(self, stream_slot: int) -> None:
        for idx in list(self.plane.updating):
            st = self.plane.stage.get(idx) or {}
            wait = int(st.get("wait_slot") or (st.get("slot") or 0) + 1)
            # txn-grouped: publish when we have pair+bins after the tx, or slot advanced
            if stream_slot < wait and not st.get("sig"):
                continue
            proto = self.plane.proto_of.get(idx)
            ok = False
            rx = int(st.get("rx") or _mono())
            slot = int(st.get("slot") or stream_slot)
            if proto == live.PROTO_DLMM:
                ok = self.publish_dlmm(idx, slot, rx)
            elif proto == live.PROTO_PUMP:
                ok = self.publish_pump(idx, slot, rx)
            if ok:
                self.plane.stage.pop(idx, None)

    def bootstrap_rpc(self) -> None:
        keys = self.plane.keys()
        print(f"STATE-007  bootstrap RPC n={len(keys)}", flush=True)
        accs = d.get_multiple(keys, retries=3)
        ctx_slot = 0
        extra: list[str] = []
        univ = sm.load_univ()
        by_idx = {int(p.get("idx") or -1): p for p in univ.get("pools") or []}
        for i, pk in enumerate(keys):
            a = accs[i] if i < len(accs) else None
            if not a or not a.get("data"):
                continue
            slot = int(a.get("slot") or 0)
            ctx_slot = max(ctx_slot, slot)
            ev = {
                "pubkey": pk,
                "slot": slot,
                "write_version": 0,
                "data": a["data"],
                "t_rx": _mono(),
                "txn_sig": None,
            }
            self.plane.bytes[pk] = ev
            self.plane.last_wv[pk] = 0
            for dep in self.plane.sub["accounts"].get(pk) or []:
                if dep["role"] == sm.ROLE_DLMM_PAIR:
                    try:
                        lb = d.parse_lbpair(a["data"])
                    except Exception:
                        continue
                    pair = by_idx.get(int(dep["pool_idx"]), {}).get("pubkey") or pk
                    for bi in d.array_indexes(lb["active_id"]):
                        bpk = d.bin_array_pda(pair, bi)
                        extra.append(bpk)
                        self.plane.pool_acc[int(dep["pool_idx"])][bpk] = sm.ROLE_DLMM_BIN
                        self.plane.sub["accounts"].setdefault(bpk, []).append(
                            {"pool_idx": int(dep["pool_idx"]), "role": sm.ROLE_DLMM_BIN, "kind": "dlmm"}
                        )
                if dep["role"] == sm.ROLE_PUMP_POOL:
                    p = live.parse_pump_pool(a["data"])
                    if not p:
                        continue
                    vb = live.b58e(p["vault_base"])
                    vq = live.b58e(p["vault_quote"])
                    idx = int(dep["pool_idx"])
                    self.plane.pool_acc[idx][vb] = sm.ROLE_PUMP_VAULT_BASE
                    self.plane.pool_acc[idx][vq] = sm.ROLE_PUMP_VAULT_QUOTE
                    extra.extend([vb, vq])
                    for role, k in ((sm.ROLE_PUMP_VAULT_BASE, vb), (sm.ROLE_PUMP_VAULT_QUOTE, vq)):
                        self.plane.sub["accounts"].setdefault(k, []).append(
                            {"pool_idx": idx, "role": role, "kind": "pump"}
                        )
        extra = [k for k in dict.fromkeys(extra) if k not in self.plane.bytes]
        if extra:
            accs2 = d.get_multiple(extra, retries=3)
            for i, pk in enumerate(extra):
                a = accs2[i] if i < len(accs2) else None
                if not a or not a.get("data"):
                    continue
                slot = int(a.get("slot") or 0)
                ctx_slot = max(ctx_slot, slot)
                self.plane.bytes[pk] = {
                    "pubkey": pk, "slot": slot, "write_version": 0,
                    "data": a["data"], "t_rx": _mono(), "txn_sig": None,
                }
        self.plane.bootstrap_slot = ctx_slot
        self.m.bootstrap_slot = ctx_slot
        # Replay stream buffer newer than RPC snapshot.
        for ev in list(self.plane.buf):
            if ev["slot"] > ctx_slot or (
                ev["slot"] == ctx_slot and ev["write_version"] > 0
            ):
                self.apply_update(ev, from_buf=True)
        self.plane.buf.clear()
        # Publish every pool that has a full set.
        for p in self.plane.sub["pools"]:
            idx = p["idx"]
            if p["kind"] == "dlmm":
                self.publish_dlmm(idx, ctx_slot, _mono())
            else:
                self.publish_pump(idx, ctx_slot, _mono())
        if self.plane.stream_slot >= ctx_slot and ctx_slot > 0:
            self.mark_ready()
        else:
            self.mark_uncertain(
                f"continuity stream_slot={self.plane.stream_slot} bootstrap={ctx_slot}"
            )

    def decode_loop(self) -> None:
        while not self.stop.is_set():
            try:
                ev = self.q.get(timeout=0.05)
            except queue.Empty:
                if self.plane.ready:
                    self.maybe_publish(self.plane.stream_slot)
                continue
            kind = ev.get("kind")
            if kind == "slot":
                prev = self.plane.stream_slot
                self.plane.stream_slot = ev["slot"]
                self.m.stream_slot = ev["slot"]
                if prev and ev["slot"] > prev + 32:
                    self.mark_uncertain(f"slot_gap {prev}->{ev['slot']}")
                    continue
                if self.plane.bootstrapping and self.plane.stream_slot > 0 and ev.get("do_boot"):
                    pass
                if self.plane.ready:
                    self.maybe_publish(self.plane.stream_slot)
                continue
            if kind == "account":
                if self.plane.bootstrapping:
                    self.plane.buf.append(ev)
                    if len(self.plane.buf) > 20000:
                        self.plane.buf = self.plane.buf[-10000:]
                    continue
                self.apply_update(ev)
                self.maybe_publish(self.plane.stream_slot)
                self.j.put(ev)

    def journal_loop(self) -> None:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as f:
            while not self.stop.is_set():
                try:
                    ev = self.j.get(timeout=0.2)
                except queue.Empty:
                    continue
                rec = {
                    "t_rx": ev.get("t_rx"),
                    "utc": ev.get("utc"),
                    "slot": ev.get("slot"),
                    "write_version": ev.get("write_version"),
                    "pubkey": ev.get("pubkey"),
                    "owner": ev.get("owner"),
                    "lamports": ev.get("lamports"),
                    "dlen": ev.get("dlen"),
                    "pool_idx": [x["pool_idx"] for x in (self.plane.sub["accounts"].get(ev.get("pubkey") or "") or [])],
                    "role": [x["role"] for x in (self.plane.sub["accounts"].get(ev.get("pubkey") or "") or [])],
                }
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                if self.m.updates % 64 == 0:
                    f.flush()

    def metrics_loop(self) -> None:
        while not self.stop.is_set():
            time.sleep(5)
            METRICS.write_text(
                json.dumps(
                    {
                        "ready": self.plane.ready,
                        "updates": self.m.updates,
                        "unique_accounts": len(self.m.unique),
                        "pools_mutated": len(self.m.pools_mutated),
                        "published": self.m.published,
                        "updating": self.m.updating,
                        "updating_max": self.m.updating_max,
                        "reconnects": self.m.reconnects,
                        "gaps": self.m.gaps,
                        "decode_fail": self.m.decode_fail,
                        "dup": self.m.dup,
                        "ooo": self.m.ooo,
                        "stale_wv": self.m.stale_wv,
                        "mismatch": self.m.mismatch,
                        "rpc_lag": self.m.rpc_lag,
                        "exact": self.m.exact,
                        "stream_slot": self.m.stream_slot,
                        "bootstrap_slot": self.m.bootstrap_slot,
                        "lat_ns": {
                            "decode": {k: _pct(self.m.lat_dec, p) for k, p in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99), ("p999", 0.999))},
                            "updating": {k: _pct(self.m.lat_upd, p) for k, p in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99), ("p999", 0.999))},
                            "publish": {k: _pct(self.m.lat_pub, p) for k, p in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99), ("p999", 0.999))},
                            "mut_to_synced": {k: _pct(self.m.lat_sync, p) for k, p in (("p50", 0.50), ("p90", 0.90), ("p99", 0.99), ("p999", 0.999))},
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(
                f"STATE-007  up ready={int(self.plane.ready)} upd={self.m.updates} "
                f"pub={self.m.published} updating={self.m.updating} "
                f"recon={self.m.reconnects} gaps={self.m.gaps} "
                f"slot={self.m.stream_slot} dec_p50={_pct(self.m.lat_dec, 0.5)}",
                flush=True,
            )

    def compare_loop(self) -> None:
        while not self.stop.is_set():
            time.sleep(COMPARE_S)
            if not self.plane.ready:
                continue
            rows = []
            checked = 0
            for p in self.plane.sub["pools"]:
                if p["kind"] != "dlmm" or checked >= 6:
                    continue
                pk = p["pubkey"]
                if not pk:
                    continue
                checked += 1
                try:
                    sys.path.insert(0, "/home/louis/arb-cap/state005")
                    from rebuild_univ import fetch_priced  # type: ignore
                    priced = fetch_priced(pk)
                except Exception as ex:
                    rows.append({"pool": pk[:8], "err": type(ex).__name__})
                    continue
                if not priced:
                    continue
                local = None
                pair = None
                bins = []
                for acc, role in self.plane.pool_acc.get(p["idx"], {}).items():
                    row = self.plane.bytes.get(acc)
                    if not row:
                        continue
                    if role == sm.ROLE_DLMM_PAIR:
                        pair = row["data"]
                    elif role == sm.ROLE_DLMM_BIN:
                        bins.append(row["data"])
                if pair:
                    local = snap_from_accounts(pair, bins)
                if not local:
                    continue
                loc_slot = 0
                for acc, role in self.plane.pool_acc.get(p["idx"], {}).items():
                    row = self.plane.bytes.get(acc)
                    if row:
                        loc_slot = max(loc_slot, int(row.get("slot") or 0))
                rpc_slot = int(priced.get("slot") or 0)
                lb_l = local["lb"]
                lb_r = priced["snap"]["lb"]
                fields = (
                    "active_id", "vol_acc", "vol_ref", "idx_ref",
                    "bin_step", "base_factor", "variable_fee_control",
                )
                bad = [f for f in fields if lb_l.get(f) != lb_r.get(f)]
                by_l = {b["id"]: (b["x"], b["y"]) for b in local["bins"]}
                by_r = {b["id"]: (b["x"], b["y"]) for b in priced["snap"]["bins"] if abs(b["id"] - lb_r["active_id"]) <= live.K}
                bin_bad = 0
                for i, xy in by_r.items():
                    if by_l.get(i) != xy:
                        bin_bad += 1
                disagree = bool(bad or bin_bad)
                if disagree and rpc_slot and loc_slot and rpc_slot < loc_slot:
                    self.m.rpc_lag += 1
                    rows.append({
                        "idx": p["idx"], "ok": None, "class": "rpc_lag",
                        "fields": bad, "bin_bad": bin_bad,
                        "rpc_slot": rpc_slot, "stream_slot": loc_slot,
                    })
                    continue
                ok = not disagree
                if ok:
                    self.m.exact += 1
                    klass = "exact"
                else:
                    self.m.mismatch += 1
                    klass = "mismatch"
                    self.invalidate(p["idx"], _mono(), self.plane.stream_slot)
                    print(
                        f"STATE-007  MISMATCH idx={p['idx']} fields={bad} "
                        f"bins={bin_bad} rpc_slot={rpc_slot} stream_slot={loc_slot}",
                        flush=True,
                    )
                rows.append({
                    "idx": p["idx"], "ok": ok, "class": klass,
                    "fields": bad, "bin_bad": bin_bad,
                    "rpc_slot": rpc_slot, "stream_slot": loc_slot,
                })
            COMPARE.write_text(json.dumps({"ts": _utc(), "rows": rows}, indent=2) + "\n", encoding="utf-8")

    def _subscribe_req(self):
        keys = self.plane.keys()
        req = geyser_pb2.SubscribeRequest()
        acc = geyser_pb2.SubscribeRequestFilterAccounts()
        acc.account.extend(keys)
        req.accounts["univ"].CopyFrom(acc)
        sl = geyser_pb2.SubscribeRequestFilterSlots()
        sl.filter_by_commitment = True
        req.slots["s"].CopyFrom(sl)
        req.commitment = geyser_pb2.PROCESSED
        return req

    def _req_iter(self):
        yield self._subscribe_req()
        while not self.stop.is_set():
            try:
                yield self.req_q.get(timeout=1.0)
            except queue.Empty:
                ping = geyser_pb2.SubscribeRequest()
                ping.ping.id = 1
                yield ping

    def grpc_loop(self) -> None:
        if geyser_pb2 is None:
            raise RuntimeError("geyser proto not generated")
        token = config.x_token()
        if not token:
            raise RuntimeError("SHYFT_X_TOKEN/SHYFT_KEY missing")
        host = config.grpc_url()
        creds = grpc.ssl_channel_credentials()
        opts = (
            ("grpc.max_receive_message_length", 1024 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 10_000),
            ("grpc.keepalive_timeout_ms", 5_000),
            ("grpc.http2.min_time_between_pings_ms", 10_000),
        )
        booted = False
        while not self.stop.is_set():
            try:
                channel = grpc.secure_channel(host, creds, options=opts)
                stub = geyser_pb2_grpc.GeyserStub(channel)
                print(f"STATE-007  connect host={host.split(':')[0]} region={config.region()}", flush=True)
                for upd in stub.Subscribe(self._req_iter(), metadata=(("x-token", token),)):
                    t_rx = _mono()  # first userspace observation
                    utc = _utc()
                    if upd.HasField("ping"):
                        pong = geyser_pb2.SubscribeRequest()
                        pong.ping.id = 1
                        self.req_q.put(pong)
                        continue
                    if upd.HasField("pong"):
                        continue
                    if upd.HasField("slot"):
                        self.q.put({"kind": "slot", "slot": int(upd.slot.slot), "t_rx": t_rx})
                        if not booted and int(upd.slot.slot) > 0:
                            booted = True
                            threading.Thread(target=self.bootstrap_rpc, name="s007-boot", daemon=True).start()
                        continue
                    if upd.HasField("account"):
                        info = upd.account.account
                        pk = _b58(info.pubkey)
                        self.m.updates += 1
                        self.m.unique.add(pk)
                        ev = {
                            "kind": "account",
                            "t_rx": t_rx,
                            "utc": utc,
                            "slot": int(upd.account.slot),
                            "write_version": int(info.write_version),
                            "pubkey": pk,
                            "owner": _b58(info.owner),
                            "lamports": int(info.lamports),
                            "dlen": len(info.data),
                            "data": bytes(info.data),
                            "txn_sig": bytes(info.txn_signature) if info.txn_signature else None,
                        }
                        self.q.put(ev)
            except grpc.RpcError as ex:
                self.m.reconnects += 1
                code = ex.code().name if hasattr(ex, "code") else "RPC"
                self.mark_uncertain(f"grpc {code}")
            except Exception as ex:
                self.m.reconnects += 1
                self.mark_uncertain(f"grpc {type(ex).__name__}")
                self.plane.bootstrapping = True
                booted = False
                time.sleep(1.5)

    def run(self) -> int:
        config.load_env()
        print(
            "STATE-007  Shyft Yellowstone FRA  FUNDED=0  "
            f"pools={self.plane.sub['n_pool']} accounts={self.plane.sub['n_account']}",
            flush=True,
        )
        threading.Thread(target=self.decode_loop, name="s007-decode", daemon=True).start()
        threading.Thread(target=self.journal_loop, name="s007-journal", daemon=True).start()
        threading.Thread(target=self.metrics_loop, name="s007-metrics", daemon=True).start()
        threading.Thread(target=self.compare_loop, name="s007-compare", daemon=True).start()
        try:
            self.grpc_loop()
        except KeyboardInterrupt:
            self.stop.set()
        return 0


def main() -> int:
    return State007().run()


if __name__ == "__main__":
    raise SystemExit(main())
