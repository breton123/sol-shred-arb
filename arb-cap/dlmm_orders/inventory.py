"""DLMM-ORDERS-001 — official inventory layers vs CORE-003 MM-only.

Source of truth: FiredancerNode/.../dlmm-sdk/commons
  extensions/bin.rs::get_limit_order_amounts_by_direction
  extensions/bin.rs::get_max_amount_out_with_limit_orders
  quote.rs::get_exact_in_fill_amount_result  (MM → processed remaining → open)
  extensions/lb_pair.rs::is_support_limit_order
  conversions/function_type.rs  (0 Undetermined, 1 LiquidityMining, 2 LimitOrder)

total_processing_order_amount is bookkeeping. It is not a fillable reserve.
processed_order_remaining_amount is the fillable processing layer.
"""
from __future__ import annotations

import struct
from typing import Any

BIN_SIZE = 144
MAX_BIN = 70
BINS_OFF = 48

FN_UNDETERMINED = 0
FN_LIQUIDITY_MINING = 1
FN_LIMIT_ORDER = 2


def parse_bin(raw: bytes, off: int = 0) -> dict[str, int]:
    if len(raw) < off + BIN_SIZE:
        raise ValueError("short bin")
    ax, ay = struct.unpack_from("<QQ", raw, off)
    price_lo, price_hi = struct.unpack_from("<QQ", raw, off + 16)
    liq_lo, liq_hi = struct.unpack_from("<QQ", raw, off + 32)
    fox, foy = struct.unpack_from("<QQ", raw, off + 48)
    fee_ask, fee_bid = struct.unpack_from("<QQ", raw, off + 64)
    open_amt, proc_total, proc_rem = struct.unpack_from("<QQQ", raw, off + 112)
    age, ask, *_ = struct.unpack_from("<IBBBB", raw, off + 136)
    return {
        "amount_x": ax,
        "amount_y": ay,
        "price": price_lo | (price_hi << 64),
        "liquidity_supply": liq_lo | (liq_hi << 64),
        "fulfilled_order_amount_x": fox,
        "fulfilled_order_amount_y": foy,
        "limit_order_fee_ask_side": fee_ask,
        "limit_order_fee_bid_side": fee_bid,
        "open_order_amount": open_amt,
        "total_processing_order_amount": proc_total,
        "processed_order_remaining_amount": proc_rem,
        "order_age": age,
        "limit_order_ask_side": ask,
    }


def parse_bin_array(data: bytes) -> list[dict[str, int]]:
    if len(data) < 10136:
        return []
    body = data[8:] if len(data) >= 10136 else data
    index = struct.unpack_from("<q", body, 0)[0]
    lo = int(index) * MAX_BIN
    out = []
    for i in range(MAX_BIN):
        b = parse_bin(body, BINS_OFF + i * BIN_SIZE)
        b["id"] = lo + i
        out.append(b)
    return out


def pack_bin(
    *,
    amount_x: int = 0,
    amount_y: int = 0,
    open_order_amount: int = 0,
    total_processing_order_amount: int = 0,
    processed_order_remaining_amount: int = 0,
    limit_order_ask_side: int = 0,
    order_age: int = 0,
    price: int = 0,
) -> bytes:
    buf = bytearray(BIN_SIZE)
    struct.pack_into("<QQ", buf, 0, amount_x, amount_y)
    struct.pack_into("<QQ", buf, 16, price & ((1 << 64) - 1), price >> 64)
    struct.pack_into(
        "<QQQ",
        buf,
        112,
        open_order_amount,
        total_processing_order_amount,
        processed_order_remaining_amount,
    )
    struct.pack_into("<I", buf, 136, order_age)
    buf[140] = limit_order_ask_side & 0xFF
    return bytes(buf)


def is_support_limit_order(function_type: int, reward_mints_all_default: bool = True) -> bool:
    if function_type == FN_LIMIT_ORDER:
        return True
    if function_type == FN_LIQUIDITY_MINING:
        return False
    if function_type == FN_UNDETERMINED:
        return bool(reward_mints_all_default)
    return False


def limit_order_amounts_by_direction(bin: dict[str, int], swap_for_y: bool) -> tuple[int, int]:
    """Returns (open_order_amount, processed_order_remaining_amount) or (0, 0)."""
    is_ask = int(bin.get("limit_order_ask_side") or 0) != 0
    if (swap_for_y and not is_ask) or ((not swap_for_y) and is_ask):
        return (
            int(bin.get("open_order_amount") or 0),
            int(bin.get("processed_order_remaining_amount") or 0),
        )
    return (0, 0)


def mm_amount(bin: dict[str, int], swap_for_y: bool) -> int:
    return int(bin["amount_y"] if swap_for_y else bin["amount_x"])


def available_output(
    bin: dict[str, int],
    swap_for_y: bool,
    *,
    support_limit_order: bool = True,
) -> int:
    """Official max out: MM + matching-side (open + processed remaining)."""
    mm = mm_amount(bin, swap_for_y)
    if not support_limit_order:
        return mm
    open_amt, proc_rem = limit_order_amounts_by_direction(bin, swap_for_y)
    return mm + open_amt + proc_rem


def kernel_available_output(bin: dict[str, int], swap_for_y: bool) -> int:
    """CORE-003 fill_mm: amount_y or amount_x only."""
    return mm_amount(bin, swap_for_y)


def fill_layers(
    bin: dict[str, int],
    leftover_out: int,
    swap_for_y: bool,
    *,
    support_limit_order: bool = True,
) -> dict[str, int]:
    """Consume leftover_out against MM, then processed remaining, then open.

    leftover_out is output tokens, not input. Used to prove layer order, not
    to replace the C fee walk.
    """
    mm = mm_amount(bin, swap_for_y)
    take_mm = min(leftover_out, mm)
    left = leftover_out - take_mm
    take_proc = 0
    take_open = 0
    if support_limit_order and left > 0:
        open_amt, proc_rem = limit_order_amounts_by_direction(bin, swap_for_y)
        take_proc = min(left, proc_rem)
        left -= take_proc
        take_open = min(left, open_amt)
        left -= take_open
    return {
        "mm": take_mm,
        "processed_remaining": take_proc,
        "open": take_open,
        "unfilled": left,
    }


def placement_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    keys = (
        "amount_x",
        "amount_y",
        "open_order_amount",
        "total_processing_order_amount",
        "processed_order_remaining_amount",
        "limit_order_ask_side",
        "fulfilled_order_amount_x",
        "fulfilled_order_amount_y",
    )
    return {k: int(after.get(k) or 0) - int(before.get(k) or 0) for k in keys}


def mm_unchanged(delta: dict[str, int]) -> bool:
    return delta.get("amount_x", 0) == 0 and delta.get("amount_y", 0) == 0


def summarize_bins(bins: list[dict[str, int]]) -> dict[str, Any]:
    hidden = []
    for b in bins:
        o = int(b.get("open_order_amount") or 0)
        p = int(b.get("processed_order_remaining_amount") or 0)
        if o or p:
            hidden.append({
                "id": b.get("id"),
                "x": b.get("amount_x"),
                "y": b.get("amount_y"),
                "open": o,
                "proc_rem": p,
                "proc_total": b.get("total_processing_order_amount"),
                "ask": b.get("limit_order_ask_side"),
            })
    return {"nbins": len(bins), "bins_with_order_inventory": hidden}
