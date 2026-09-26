"""Offline fill_bin: MM → processed remaining → matching-side open.

Does not import or patch CORE-003. Fee=0 / price=2^64 fixtures first.
S' mutates each layer separately. Order takes never debit amount_x/y.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from inventory import (
    FN_LIMIT_ORDER,
    is_support_limit_order,
    limit_order_amounts_by_direction,
    mm_amount,
)

Q1 = 1 << 64


def _amount_out(amount: int, price: int, swap_for_y: bool) -> int:
    if price == Q1:
        return amount
    raise NotImplementedError("fixture kernel is Q1-only")


def _amount_in(out: int, price: int, swap_for_y: bool) -> int:
    if price == Q1:
        return out
    raise NotImplementedError("fixture kernel is Q1-only")


def _fill_against(max_out: int, amount: int, price: int, swap_for_y: bool) -> tuple[int, int, int]:
    if max_out == 0:
        return 0, amount, 0
    max_in = _amount_in(max_out, price, swap_for_y)
    if amount >= max_in:
        return max_in, amount - max_in, max_out
    return amount, 0, _amount_out(amount, price, swap_for_y)


@dataclass
class OBin:
    id: int = 0
    amount_x: int = 0
    amount_y: int = 0
    processed_order_remaining_amount: int = 0
    open_order_amount: int = 0
    total_processing_order_amount: int = 0
    order_age: int = 0
    limit_order_ask_side: int = 0
    price: int = Q1


@dataclass
class OState:
    active_id: int = 0
    bin_step: int = 1
    status: int = 0
    function_type: int = FN_LIMIT_ORDER
    reward_mint_live_mask: int = 0
    reserve_x: int = 0
    reserve_y: int = 0
    bins: list[OBin] = field(default_factory=list)


@dataclass
class Fill:
    mm_in: int = 0
    mm_out: int = 0
    proc_in: int = 0
    proc_out: int = 0
    open_in: int = 0
    open_out: int = 0
    used_in: int = 0
    left: int = 0
    out_amt: int = 0


def orders_enabled(s: OState) -> bool:
    return is_support_limit_order(s.function_type, s.reward_mint_live_mask == 0)


def fill_mm(bin: OBin, amount: int, swap_for_y: bool) -> tuple[int, int, int]:
    return _fill_against(mm_amount(bin.__dict__, swap_for_y), amount, bin.price, swap_for_y)


def fill_processed_order(bin: OBin, amount: int, swap_for_y: bool, orders_on: bool) -> tuple[int, int, int]:
    d = bin.__dict__
    _, proc = limit_order_amounts_by_direction(d, swap_for_y) if orders_on else (0, 0)
    if not orders_on:
        proc = 0
    return _fill_against(proc, amount, bin.price, swap_for_y)


def fill_open_orders(bin: OBin, amount: int, swap_for_y: bool, orders_on: bool) -> tuple[int, int, int]:
    d = bin.__dict__
    open_amt, _ = limit_order_amounts_by_direction(d, swap_for_y) if orders_on else (0, 0)
    if not orders_on:
        open_amt = 0
    return _fill_against(open_amt, amount, bin.price, swap_for_y)


def fill_bin(bin: OBin, amount: int, swap_for_y: bool, orders_on: bool) -> Fill:
    mm_in, left, mm_out = fill_mm(bin, amount, swap_for_y)
    proc_in, left, proc_out = fill_processed_order(bin, left, swap_for_y, orders_on)
    open_in, left, open_out = fill_open_orders(bin, left, swap_for_y, orders_on)
    return Fill(
        mm_in=mm_in, mm_out=mm_out,
        proc_in=proc_in, proc_out=proc_out,
        open_in=open_in, open_out=open_out,
        used_in=mm_in + proc_in + open_in,
        left=left,
        out_amt=mm_out + proc_out + open_out,
    )


def apply_fill(bin: OBin, s: OState, swap_for_y: bool, f: Fill) -> None:
    if swap_for_y:
        if bin.amount_y < f.mm_out:
            raise ValueError("mm y")
        bin.amount_y -= f.mm_out
        bin.amount_x += f.mm_in
        s.reserve_y -= f.out_amt
        s.reserve_x += f.used_in
    else:
        if bin.amount_x < f.mm_out:
            raise ValueError("mm x")
        bin.amount_x -= f.mm_out
        bin.amount_y += f.mm_in
        s.reserve_x -= f.out_amt
        s.reserve_y += f.used_in
    if bin.processed_order_remaining_amount < f.proc_out or bin.open_order_amount < f.open_out:
        raise ValueError("order inventory")
    bin.processed_order_remaining_amount -= f.proc_out
    bin.open_order_amount -= f.open_out


def _find(s: OState, bid: int) -> Optional[OBin]:
    for b in s.bins:
        if b.id == bid:
            return b
    return None


def apply_swap(before: OState, amount_in: int, swap_for_y: bool) -> tuple[OState, dict]:
    """Fee-zero exact-in. Quote and S' both required for fixtures."""
    after = replace(before, bins=[replace(b) for b in before.bins])
    on = orders_enabled(after)
    left = amount_in
    total_out = 0
    guard = 0
    while left > 0 and guard < 256:
        guard += 1
        bin = _find(after, after.active_id)
        if bin is None:
            raise ValueError("missing bin")
        f = fill_bin(bin, left, swap_for_y, on)
        if f.out_amt == 0 and f.used_in == 0:
            if swap_for_y:
                after.active_id -= 1
            else:
                after.active_id += 1
            continue
        apply_fill(bin, after, swap_for_y, f)
        left -= f.used_in
        total_out += f.out_amt
        if left > 0:
            if swap_for_y:
                after.active_id -= 1
            else:
                after.active_id += 1
    if left > 0:
        raise ValueError("unfilled")
    return after, {"amount_in": amount_in, "amount_out": total_out, "active_id_after": after.active_id}


def bin_snap(b: OBin) -> dict:
    return {
        "id": b.id,
        "amount_x": b.amount_x,
        "amount_y": b.amount_y,
        "processed_order_remaining_amount": b.processed_order_remaining_amount,
        "open_order_amount": b.open_order_amount,
        "limit_order_ask_side": b.limit_order_ask_side,
    }
