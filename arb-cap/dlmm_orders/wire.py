"""AUTH blob v2 draft. Not used by live001.write_dlmm / STATE-010.

v1: per bin id + x + y
v2: pool function_type + reward_mask; per bin + proc_rem + open + ask
Same BinArray wait set. Richer representation only.
"""
from __future__ import annotations

import struct


def write_bin_v2(buf: bytearray, b: dict) -> None:
    buf += struct.pack("<i", int(b["id"]))
    buf += struct.pack("<Q", int(b.get("x") if "x" in b else b["amount_x"]))
    buf += struct.pack("<Q", int(b.get("y") if "y" in b else b["amount_y"]))
    buf += struct.pack("<Q", int(b.get("proc_rem", b.get("processed_order_remaining_amount", 0))))
    buf += struct.pack("<Q", int(b.get("open", b.get("open_order_amount", 0))))
    buf += bytes([int(b.get("ask", b.get("limit_order_ask_side", 0))) & 0xFF])
    buf += bytes(7)


def write_pool_gate(buf: bytearray, function_type: int, reward_mask: int) -> None:
    buf += bytes([function_type & 0xFF, reward_mask & 0xFF])
