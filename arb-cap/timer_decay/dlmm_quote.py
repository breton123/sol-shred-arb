"""Bit-faithful ports of meteora_dlmm.c + pump.c + cycle.c. Research only."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

U64 = (1 << 64) - 1
U128 = (1 << 128) - 1
FEE_PREC = 1_000_000_000
MAX_FEE = 100_000_000
BPS = 10_000
SCALE = 64
ONE_Q64 = 1 << SCALE
MIN_BIN = -443636
MAX_BIN = 443636
PUMP_DEN = 10_000


def _mul_shr64(a: int, b: int, round_up: bool) -> Optional[int]:
    a0, a1 = a & U64, a >> 64
    b0, b1 = b & U64, b >> 64
    p00 = a0 * b0
    p01 = a0 * b1
    p10 = a1 * b0
    p11 = a1 * b1
    mid = (p00 >> 64) + (p01 & U64) + (p10 & U64)
    hi = p11 + (p01 >> 64) + (p10 >> 64) + (mid >> 64)
    if hi != 0:
        return None
    r = mid & U64
    if round_up and (p00 & U64) != 0:
        if r == U128:
            return None
        r += 1
    return r


def _shl64_div(num: int, den: int, round_up: bool) -> Optional[int]:
    if den == 0 or num > (U128 >> 64):
        return None
    q = (num << 64) // den
    rem = (num << 64) % den
    if round_up and rem:
        if q == U128:
            return None
        q += 1
    return q


def price_from_id(bin_id: int, bin_step: int) -> Optional[int]:
    if bin_id == 0:
        return ONE_Q64
    invert = bin_id < 0
    exp = -bin_id if invert else bin_id
    if exp >= 0x80000:
        return None
    bps = (bin_step << SCALE) // BPS
    base = ONE_Q64 + bps
    squared = base
    result = ONE_Q64
    if squared >= result:
        squared = U128 // squared
        invert = not invert
    for bit in range(19):
        if exp & (1 << bit):
            tmp = _mul_shr64(result, squared, False)
            if tmp is None:
                return None
            result = tmp
        if bit + 1 < 19:
            tmp = _mul_shr64(squared, squared, False)
            if tmp is None:
                return None
            squared = tmp
    if result == 0:
        return None
    if invert:
        result = U128 // result
    return result


def amount_out(amt_in: int, price: int, swap_for_y: bool) -> Optional[int]:
    if swap_for_y:
        r = _mul_shr64(price, amt_in, False)
    else:
        r = _shl64_div(amt_in, price, False)
    if r is None or r > U64:
        return None
    return r


def amount_in(amt_out: int, price: int, swap_for_y: bool, round_up: bool) -> Optional[int]:
    if swap_for_y:
        r = _shl64_div(amt_out, price, round_up)
    else:
        r = _mul_shr64(amt_out, price, round_up)
    if r is None or r > U64:
        return None
    return r


@dataclass
class Bin:
    id: int
    x: int
    y: int
    price: int = 0


@dataclass
class Dlmm:
    active_id: int
    bin_step: int
    status: int
    base_factor: int
    filter_period: int
    decay_period: int
    reduction_factor: int
    variable_fee_control: int
    max_volatility_accumulator: int
    protocol_share: int
    base_fee_power_factor: int
    collect_fee_mode: int
    vol_acc: int
    vol_ref: int
    idx_ref: int
    last_upd: int
    reserve_x: int
    reserve_y: int
    now_ts: int
    bins: list = field(default_factory=list)


@dataclass
class Pump:
    reserve_base: int
    reserve_quote: int
    virtual_quote: int
    lp_fee_bps: int
    protocol_fee_bps: int
    creator_fee_bps: int
    disabled: int
    status: int


def clone_dlmm(s: Dlmm) -> Dlmm:
    return Dlmm(
        s.active_id, s.bin_step, s.status, s.base_factor, s.filter_period,
        s.decay_period, s.reduction_factor, s.variable_fee_control,
        s.max_volatility_accumulator, s.protocol_share, s.base_fee_power_factor,
        s.collect_fee_mode, s.vol_acc, s.vol_ref, s.idx_ref, s.last_upd,
        s.reserve_x, s.reserve_y, s.now_ts,
        [Bin(b.id, b.x, b.y, b.price) for b in s.bins],
    )


def total_fee_rate(s: Dlmm) -> Optional[int]:
    base = s.base_factor * s.bin_step * 10
    pow10 = 10 ** s.base_fee_power_factor
    base *= pow10
    variable = 0
    if s.variable_fee_control > 0:
        vfa = s.vol_acc * s.bin_step
        v_fee = s.variable_fee_control * vfa * vfa
        variable = (v_fee + 99_999_999_999) // 100_000_000_000
    total = base + variable
    if total > MAX_FEE:
        total = MAX_FEE
    return total


def update_references(s: Dlmm) -> None:
    elapsed = s.now_ts - s.last_upd
    if elapsed >= s.filter_period:
        s.idx_ref = s.active_id
        if elapsed < s.decay_period:
            s.vol_ref = (s.vol_acc * s.reduction_factor) // BPS
        else:
            s.vol_ref = 0


def update_volatility(s: Dlmm) -> None:
    delta = abs(s.idx_ref - s.active_id)
    acc = s.vol_ref + delta * BPS
    if acc > s.max_volatility_accumulator:
        acc = s.max_volatility_accumulator
    s.vol_acc = acc


def fee_on_input(s: Dlmm, swap_for_y: bool) -> bool:
    if s.collect_fee_mode == 1:
        return not swap_for_y
    return True


def compute_fee(s: Dlmm, amount: int) -> Optional[int]:
    rate = total_fee_rate(s)
    if rate is None:
        return None
    den = FEE_PREC - rate
    if den == 0:
        return None
    f = (amount * rate + den - 1) // den
    if f > U64:
        return None
    return f


def compute_fee_from_amount(s: Dlmm, amount_with_fees: int) -> Optional[int]:
    rate = total_fee_rate(s)
    if rate is None:
        return None
    f = (amount_with_fees * rate + (FEE_PREC - 1)) // FEE_PREC
    if f > U64:
        return None
    return f


def find_bin(s: Dlmm, bin_id: int) -> Optional[Bin]:
    for b in s.bins:
        if b.id == bin_id:
            return b
    return None


def fill_mm(bin: Bin, amount: int, swap_for_y: bool):
    max_out = bin.y if swap_for_y else bin.x
    if max_out == 0:
        return 0, amount, 0
    max_in = amount_in(max_out, bin.price, swap_for_y, True)
    if max_in is None:
        return None
    if amount >= max_in:
        return max_in, amount - max_in, max_out
    out_amt = amount_out(amount, bin.price, swap_for_y)
    if out_amt is None:
        return None
    return amount, 0, out_amt


def quote_dlmm(state: Dlmm, amount_in_amt: int, swap_for_y: bool) -> Optional[int]:
    if state.status != 0 or amount_in_amt == 0:
        return None
    after = clone_dlmm(state)
    update_references(after)
    foi = fee_on_input(after, swap_for_y)
    left = amount_in_amt
    total_out = 0
    guard = 0
    while left > 0 and guard < 256:
        guard += 1
        bin = find_bin(after, after.active_id)
        if bin is None:
            return None
        if bin.price == 0:
            p = price_from_id(bin.id, after.bin_step)
            if p is None:
                return None
            bin.price = p
        update_volatility(after)
        excluded = left
        fee = 0
        if foi:
            fee = compute_fee_from_amount(after, left)
            if fee is None or fee > left:
                return None
            excluded = left - fee
        filled = fill_mm(bin, excluded, swap_for_y)
        if filled is None:
            return None
        used_in, leftover, out_amt = filled
        included = left
        if leftover > 0:
            excluded = excluded - leftover
            if foi:
                fee = compute_fee(after, excluded)
                if fee is None:
                    return None
                included = excluded + fee
            else:
                included = excluded
        if not foi:
            fee = compute_fee_from_amount(after, out_amt)
            if fee is None or fee > out_amt:
                return None
            out_amt -= fee
        if included > left:
            return None
        left -= included
        total_out += out_amt
        if left > 0:
            if swap_for_y:
                if after.active_id <= MIN_BIN:
                    return None
                after.active_id -= 1
            else:
                if after.active_id >= MAX_BIN:
                    return None
                after.active_id += 1
    if left > 0:
        return None
    return total_out


def fee_after_time(state: Dlmm, now_ts: int) -> tuple[int, int, int]:
    """Return (fee_rate, vol_acc, vol_ref) as a quote would see them after one hop update."""
    s = clone_dlmm(state)
    s.now_ts = now_ts
    update_references(s)
    update_volatility(s)
    rate = total_fee_rate(s) or 0
    return rate, s.vol_acc, s.vol_ref


def next_boundaries(state: Dlmm, now_ts: int) -> list[tuple[str, int]]:
    """Future times when update_references changes vol_ref / index_ref."""
    if state.variable_fee_control == 0:
        return []
    last = int(state.last_upd)
    fp = int(state.filter_period)
    dp = int(state.decay_period)
    out = []
    t_f = last + fp
    t_d = last + dp
    if now_ts < t_f:
        out.append(("filter", t_f))
    if now_ts < t_d and t_d != t_f:
        out.append(("decay", t_d))
    return out


def _ceil_div(n: int, d: int) -> Optional[int]:
    if d == 0:
        return None
    return n // d + (1 if n % d else 0)


def _fee_bps(n: int, bps: int) -> Optional[int]:
    if bps > PUMP_DEN:
        return None
    return _ceil_div(n * bps, PUMP_DEN)


def quote_pump(p: Pump, amount_in_amt: int, direction: int) -> Optional[int]:
    if p.status != 0 or amount_in_amt == 0:
        return None
    if direction not in (0, 1):
        return None
    disable_bit = 8 if direction == 0 else 16
    if p.disabled & disable_bit:
        return None
    total_bps = p.lp_fee_bps + p.protocol_fee_bps + p.creator_fee_bps
    if total_bps >= PUMP_DEN:
        return None
    if p.reserve_base == 0 or p.reserve_quote == 0:
        return None
    qeff = p.reserve_quote + p.virtual_quote
    if qeff <= 0 or qeff > U64:
        return None
    if direction == 1:
        gross = qeff * amount_in_amt // (p.reserve_base + amount_in_amt)
        lp = _fee_bps(gross, p.lp_fee_bps)
        proto = _fee_bps(gross, p.protocol_fee_bps)
        creator = _fee_bps(gross, p.creator_fee_bps)
        if None in (lp, proto, creator):
            return None
        fee = lp + proto + creator
        if gross < fee:
            return None
        out = gross - fee
    else:
        effective = amount_in_amt * PUMP_DEN // (PUMP_DEN + total_bps)
        lp = _fee_bps(effective, p.lp_fee_bps)
        proto = _fee_bps(effective, p.protocol_fee_bps)
        creator = _fee_bps(effective, p.creator_fee_bps)
        if None in (lp, proto, creator):
            return None
        fee = lp + proto + creator
        if effective + fee > amount_in_amt:
            effective -= effective + fee - amount_in_amt
            lp = _fee_bps(effective, p.lp_fee_bps)
            proto = _fee_bps(effective, p.protocol_fee_bps)
            creator = _fee_bps(effective, p.creator_fee_bps)
            if None in (lp, proto, creator):
                return None
            fee = lp + proto + creator
        if effective < 1:
            return None
        net = effective - 1
        out = p.reserve_base * net // (qeff + net)
        if out == 0 or out > p.reserve_base:
            return None
    if out == 0 or out > U64:
        return None
    return out


def cycle_quote(dlmm: Dlmm, pump: Pump, ain: int, direction: int, now_ts: int) -> Optional[int]:
    d = clone_dlmm(dlmm)
    d.now_ts = now_ts
    if direction == 0:
        mid = quote_dlmm(d, ain, 0)
        if mid is None:
            return None
        return quote_pump(pump, mid, 1)
    mid = quote_pump(pump, ain, 0)
    if mid is None:
        return None
    return quote_dlmm(d, mid, 1)


def hurdle(direction: int) -> int:
    cu = 169397 if direction == 0 else 179440
    return 5000 + cu + 150000 + 50000
