#!/usr/bin/env python3
"""Connectivity probe. Prints gRPC status codes only. Never prints tokens."""
from __future__ import annotations

import sys
from pathlib import Path

import grpc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "gen"))
import config  # noqa: E402
import geyser_pb2  # noqa: E402
import geyser_pb2_grpc  # noqa: E402


def host_of(url: str) -> str:
    return url.replace("https://", "").replace("http://", "")


def try_one(host: str, token: str) -> None:
    creds = grpc.ssl_channel_credentials()

    class Auth(grpc.AuthMetadataPlugin):
        def __call__(self, context, callback):
            callback((("x-token", token),), None)

    comp = grpc.composite_channel_credentials(
        creds, grpc.metadata_call_credentials(Auth())
    )
    for label, channel in (
        ("ssl+meta", grpc.secure_channel(host, creds)),
        ("ssl+callcred", grpc.secure_channel(host, comp)),
    ):
        stub = geyser_pb2_grpc.GeyserStub(channel)
        try:
            if label == "ssl+meta":
                ver = stub.GetVersion(geyser_pb2.GetVersionRequest(), metadata=(("x-token", token),), timeout=8)
            else:
                ver = stub.GetVersion(geyser_pb2.GetVersionRequest(), timeout=8)
            print(f"  {label} GetVersion OK ver_len={len(ver.version)}", flush=True)
            return
        except grpc.RpcError as ex:
            print(f"  {label} GetVersion {ex.code().name}", flush=True)
        except Exception as ex:
            print(f"  {label} GetVersion {type(ex).__name__}", flush=True)


def main() -> int:
    config.load_env()
    token = config.x_token()
    print(f"token_len={len(token)} default_host={config.grpc_url()}", flush=True)
    hosts = [
        config.grpc_url(),
        "grpc.fra.shyft.to:443",
        "grpc-fra.shyft.to:443",
        "fra.grpc.shyft.to:443",
        "grpc.eu.shyft.to:443",
        "grpc.ams.shyft.to:443",
    ]
    seen = set()
    for h in hosts:
        h = host_of(h)
        if h in seen:
            continue
        seen.add(h)
        print(f"host={h.split(':')[0]}", flush=True)
        try_one(h, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
