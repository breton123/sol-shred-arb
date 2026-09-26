from __future__ import annotations

import base64
import unittest

from alt_rpc import ALT_PROGRAM, fetch, parse_account


def _value(raw: bytes, owner: str = ALT_PROGRAM) -> dict:
    return {"owner": owner, "data": [base64.b64encode(raw).decode(), "base64"]}


class TestAltAccount(unittest.TestCase):
    def test_parses_owned_table_addresses(self):
        a, b = bytes(range(32)), bytes(range(32, 64))
        raw = (1).to_bytes(4, "little") + bytes(52) + a + b
        self.assertEqual(parse_account(_value(raw), lambda x: x), [a, b])

    def test_rejects_wrong_owner_state_and_trailing_bytes(self):
        raw = (1).to_bytes(4, "little") + bytes(52) + bytes(32)
        self.assertIsNone(parse_account(_value(raw, "wrong"), lambda x: x))
        self.assertIsNone(parse_account(_value(bytes(56) + bytes(32)), lambda x: x))
        self.assertIsNone(parse_account(_value(raw + b"x"), lambda x: x))

    def test_uses_supported_rpc_method_and_checks_rpc_error(self):
        seen = []

        def rpc(_url, method, params):
            seen.append((method, params))
            raw = (1).to_bytes(4, "little") + bytes(52) + bytes(32)
            return {"result": {"value": _value(raw)}}

        self.assertEqual(fetch(rpc, "rpc", "table", lambda x: x), [bytes(32)])
        self.assertEqual(seen, [("getAccountInfo", ["table", {"encoding": "base64"}])])
        self.assertIsNone(fetch(lambda *_: {"error": {"code": -32601}}, "rpc", "table", lambda x: x))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
