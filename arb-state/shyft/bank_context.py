"""Receipt-ordered bank evidence. IDs are scoped to one provider connection.

This is a knowledge journal, not a proof that a raw transaction from a different
feed belongs to a bank. Callers must supply an independently bound bank identity.
"""
import hashlib
import struct

SLOT_HASHES = "SysvarS1otHashes111111111111111111111111111"
SYSVAR_OWNER = "Sysvar1111111111111111111111111111111111111"


def optional_field(message, name):
    field = message.DESCRIPTOR.fields_by_name.get(name)
    if field is None:
        return None
    if field.has_presence:
        return getattr(message, name) if message.HasField(name) else None
    # Nonoptional scalar defaults do not prove that an identity was supplied.
    value = getattr(message, name)
    return value if value != field.default_value else None


def parse_slot_hashes(data):
    if len(data) < 8:
        raise ValueError("truncated SlotHashes")
    n = struct.unpack_from("<Q", data)[0]
    if n > 512 or len(data) < 8 + n * 40 or any(data[8 + n * 40:]):
        raise ValueError("invalid SlotHashes length")
    values = [struct.unpack_from("<Q32s", data, 8 + i * 40) for i in range(n)]
    if any(a[0] <= b[0] for a, b in zip(values, values[1:])):
        raise ValueError("invalid SlotHashes order")
    return [(s, h.hex()) for s, h in values]


class BankJournal:
    def __init__(self, capacity=2048):
        self.capacity = capacity
        self.generation = None
        self.records = {}

    def apply(self, event):
        kind, generation = event["kind"], event["generation"]
        if kind == "bank_generation":
            self.records.clear()
            self.generation = generation
            return "generation_started"
        if generation != self.generation or generation is None:
            return "stale_generation"
        if kind == "bank_disconnect":
            self.records.clear()
            self.generation = None
            return "disconnected"
        bank_id = event.get("bank_id")
        if bank_id is None:
            return "identity_missing"
        key = (event["slot"], bank_id)
        row = self.records.setdefault(key, {"slot": key[0], "bank_id": bank_id,
                    "parent": None, "statuses": [], "hashes": None, "conflict": False,
                    "last_rx": event["rx"]})
        if len(self.records) > self.capacity:
            self.records.pop(next(iter(self.records)))
        if event["rx"] < row["last_rx"]:
            row["conflict"] = True
            return "receipt_order_conflict"
        row["last_rx"] = event["rx"]
        if kind == "bank_slot":
            parent = event.get("parent")
            if parent is not None:
                if parent >= row["slot"] or (row["parent"] is not None and parent != row["parent"]):
                    row["conflict"] = True
                row["parent"] = parent
            if event["status"] not in row["statuses"]:
                row["statuses"].append(event["status"])
        elif kind == "bank_account":
            if event.get("startup") or event.get("owner") != SYSVAR_OWNER:
                row["conflict"] = True
                return "invalid_sysvar_provenance"
            try:
                data = bytes.fromhex(event["data_hex"])
                hashes = parse_slot_hashes(data)
            except (ValueError, TypeError):
                row["conflict"] = True
                return "invalid_sysvar_bytes"
            if (hashes and hashes[0][0] >= row["slot"]) or (row["hashes"] is not None and row["hashes"] != hashes):
                row["conflict"] = True
            row["hashes"] = hashes
            row.setdefault("hashes_rx", event["rx"])
            row["data_sha256"] = hashlib.sha256(data).hexdigest()
        if row["hashes"] and row["parent"] is not None and row["hashes"][0][0] != row["parent"]:
            row["conflict"] = True
        return "conflict" if row["conflict"] else "recorded"

    def context(self, slot, bank_id, generation, deadline):
        reason = "available"
        row = self.records.get((slot, bank_id))
        if generation is None or generation != self.generation:
            reason = "generation_unbound"
        elif bank_id is None:
            reason = "identity_missing"
        elif row is None:
            reason = "context_missing"
        elif row["last_rx"] > deadline:
            reason = "not_available_at_deadline"
        elif row["conflict"]:
            reason = "context_conflict"
        elif 6 in row["statuses"]:
            reason = "dead_bank"
        elif row["parent"] is None or not row["hashes"]:
            reason = "context_incomplete"
        return {"reason": reason, "generation": generation, "slot": slot, "bank_id": bank_id,
                "context": dict(row, statuses=list(row["statuses"]), hashes=tuple(row["hashes"])) if reason == "available" else None}
