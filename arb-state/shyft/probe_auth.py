#!/usr/bin/env python3
"""Try auth header names. Prints status codes only."""
from __future__ import annotations

import sys
from pathlib import Path

import grpc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gen"))
import config  # noqa: E402
import geyser_pb2  # noqa: E402
import geyser_pb2_grpc  # noqa: E402


def main() -> int:
    config.load_env()
    token = config.x_token()
    host = config.grpc_url()
    print(f"host={host.split(':')[0]} token_len={len(token)}", flush=True)
    stub = geyser_pb2_grpc.GeyserStub(grpc.secure_channel(host, grpc.ssl_channel_credentials()))
    variants = [
        (("x-token", token),),
        (("X-Token", token),),
        (("x-api-key", token),),
        (("authorization", token),),
        (("authorization", f"Bearer {token}"),),
        (("access-token", token),),
        (("token", token),),
    ]
    for md in variants:
        name = md[0][0]
        try:
            stub.GetVersion(geyser_pb2.GetVersionRequest(), metadata=md, timeout=6)
            print(f"  {name} OK", flush=True)
            return 0
        except grpc.RpcError as ex:
            print(f"  {name} {ex.code().name}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
