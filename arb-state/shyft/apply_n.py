"""Pack last AUTH S + geyser ix, run production state_apply."""
from __future__ import annotations

import io
import json
import os
import struct
import subprocess
from pathlib import Path

import live001 as live
import record_dlmm as d

APPLY = Path(os.environ.get(
    "STATE_APPLY",
    str(Path("/home/louis/arb-core/build/state_apply")),
))


def _b58d(pk: str) -> bytes:
    raw = d.b58d(pk) if hasattr(d, "b58d") else None
    if raw and len(raw) == 32:
        return raw
    # record_dlmm uses _pk encode; decode via solders-less table
    from record_dlmm import b58decode  # type: ignore
    return b58decode(pk)


def _pk32(pk: str) -> bytes:
    try:
        from solders.pubkey import Pubkey
        return bytes(Pubkey.from_string(pk))
    except Exception:
        pass
    alph = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in pk:
        n = n * 58 + alph.index(c)
    raw = n.to_bytes(32, "big")
    return raw


def pack_dlmm_blob(last_s: dict) -> bytes:
    bins = last_s.get("bins") or {}
    rows = []
    for k, xy in bins.items():
        bid = int(k)
        if isinstance(xy, dict):
            rows.append({"id": bid, "x": int(xy["x"]), "y": int(xy["y"])})
        else:
            rows.append({"id": bid, "x": int(xy[0]), "y": int(xy[1])})
    rows.sort(key=lambda b: b["id"])
    snap = {
        "lb": {
            "active_id": int(last_s["active_id"]),
            "bin_step": int(last_s["bin_step"]),
            "status": int(last_s.get("status") or 0),
            "base_factor": int(last_s["base_factor"]),
            "filter_period": int(last_s.get("filter_period") or 0),
            "decay_period": int(last_s.get("decay_period") or 0),
            "reduction_factor": int(last_s.get("reduction_factor") or 0),
            "variable_fee_control": int(last_s["variable_fee_control"]),
            "max_volatility_accumulator": int(last_s.get("max_volatility_accumulator") or 0),
            "protocol_share": int(last_s.get("protocol_share") or 0),
            "base_fee_power_factor": int(last_s.get("base_fee_power_factor") or 0),
            "collect_fee_mode": int(last_s.get("collect_fee_mode") or 0),
            "vol_acc": int(last_s["vol_acc"]),
            "vol_ref": int(last_s["vol_ref"]),
            "idx_ref": int(last_s["idx_ref"]),
            "last_upd": int(last_s.get("last_upd") or 0),
        },
        "bins": rows,
        "reserve_x": int(last_s["reserve_x"]),
        "reserve_y": int(last_s["reserve_y"]),
    }
    buf = io.BytesIO()
    live.write_dlmm(buf, snap)
    raw = buf.getvalue()
    # overwrite now_ts (last 8+2 before bins is ... write_i64 now then nbin)
    # write_dlmm uses time.time(); pin to last_upd so apply is deterministic
    # layout: ... last_upd i64, rx u64, ry u64, now i64, nbin u16
    # Find now: after two u64 reserves.
    # Safer: rebuild tail. live.write already wrote now; patch last 10+bins.
    # last_upd is in header; now is after reserves.
    return raw


def pack_pump_blob(last_s: dict) -> bytes:
    buf = io.BytesIO()
    vq = last_s.get("virtual_quote_reserves")
    if vq is None:
        vq = last_s.get("virtual_quote") or 0
    rb = last_s.get("base_vault_amount", last_s["reserve_base"])
    rq = last_s.get("quote_vault_amount", last_s["reserve_quote"])
    live.write_pump(buf, {
        "reserve_base": int(rb),
        "reserve_quote": int(rq),
        "virtual_quote": int(vq),
        "lp_fee_bps": int(last_s.get("lp_fee_bps") or 0),
        "protocol_fee_bps": int(last_s.get("protocol_fee_bps") or 0),
        "creator_fee_bps": int(last_s.get("creator_fee_bps") or 0),
        "disabled": int(last_s.get("disabled") or 0),
        "status": int(last_s.get("status") or 0),
    })
    return buf.getvalue()


def pack_stdin(keys: list[str], accounts: list[str], data: bytes, blob: bytes) -> bytes:
    kraw = [_pk32(k) for k in accounts]
    acc = bytes(range(len(kraw)))
    out = struct.pack("<H", len(kraw))
    out += b"".join(kraw)
    out += struct.pack("<H", len(acc)) + acc
    out += struct.pack("<H", len(data)) + data
    out += struct.pack("<H", len(blob)) + blob
    return out


def apply_ix(last_s: dict, accounts: list[str], data: bytes, blob: bytes | None = None) -> dict | None:
    if not APPLY.exists():
        return None
    kind = last_s.get("kind") or ("pump" if "reserve_base" in last_s else "dlmm")
    if blob is None:
        blob = pack_pump_blob(last_s) if kind == "pump" else pack_dlmm_blob(last_s)
    payload = pack_stdin([], accounts, data, blob)
    r = subprocess.run(
        [str(APPLY)], input=payload, capture_output=True, timeout=2,
    )
    if r.returncode != 0 or not r.stdout:
        return None
    try:
        out = json.loads(r.stdout.decode())
    except json.JSONDecodeError:
        return None
    if out.get("error"):
        return None
    return out
