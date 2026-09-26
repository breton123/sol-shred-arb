"""STATE-011 draft parse: richer bins from the same BinArray bytes.

Not imported by state008. No new Yellowstone subscriptions.
Do not AUTH this layout while STATE-010 is soaking.
"""
from __future__ import annotations

from inventory import parse_bin_array
from inventory import is_support_limit_order

# LbPair: disc8 + Static32 + Variable32 + seeds4 + active7 + extra5 + 4*32 mints/vaults
# + ProtocolFee16 + pad32 → reward_infos[0].mint
REWARD0_MINT = 8 + 32 + 32 + 4 + 7 + 5 + 128 + 16 + 32
REWARD1_MINT = REWARD0_MINT + 144
# disc + HHHH + II + ii + protocol_share u16 + base_fee_power_factor u8
FN_TYPE_OFF = 8 + 8 + 8 + 8 + 2 + 1


def parse_function_type(pair: bytes) -> int:
    if len(pair) < FN_TYPE_OFF + 1:
        raise ValueError("short pair")
    return pair[FN_TYPE_OFF]


def parse_reward_mask(pair: bytes) -> int:
    if len(pair) < REWARD1_MINT + 32:
        return 0
    mask = 0
    if pair[REWARD0_MINT : REWARD0_MINT + 32] != bytes(32):
        mask |= 1
    if pair[REWARD1_MINT : REWARD1_MINT + 32] != bytes(32):
        mask |= 2
    return mask


def parse_orders_gate(pair: bytes) -> dict:
    ft = parse_function_type(pair)
    mask = parse_reward_mask(pair)
    return {
        "function_type": ft,
        "reward_mint_live_mask": mask,
        "orders_enabled": is_support_limit_order(ft, mask == 0),
    }


def snap_bins(bin_datas: list[bytes], active_id: int, k: int = 16) -> list[dict]:
    bins = []
    for raw in bin_datas:
        bins.extend(parse_bin_array(raw))
    return [b for b in bins if abs(int(b["id"]) - active_id) <= k]


def published_s(pair: bytes, bin_datas: list[bytes], active_id: int) -> dict:
    """Canonical STATE-011 S. Barrier accounts unchanged."""
    gate = parse_orders_gate(pair)
    bins = snap_bins(bin_datas, active_id)
    return {
        **gate,
        "bins": {
            int(b["id"]): {
                "x": b["amount_x"],
                "y": b["amount_y"],
                "proc_rem": b["processed_order_remaining_amount"],
                "open": b["open_order_amount"],
                "ask": b["limit_order_ask_side"],
            }
            for b in bins
        },
    }
