"""STATE-007 env. Never print tokens or auth metadata."""
from __future__ import annotations

import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("\r"))


def load_env() -> None:
    _load_env_file(Path.home() / ".arb-state007.env")
    _load_env_file(Path.home() / ".arb-smoke.env")


def grpc_url() -> str:
    raw = (
        os.environ.get("SHYFT_GRPC_URL")
        or os.environ.get("GRPC_URL")
        or "https://grpc.fra.shyft.to"
    ).strip()
    raw = raw.replace("https://", "").replace("http://", "")
    if ":" not in raw:
        raw = raw + ":443"
    return raw


def x_token() -> str:
    # Yellowstone x-token from the Shyft gRPC dashboard — not the REST API key.
    return (
        os.environ.get("SHYFT_X_TOKEN")
        or os.environ.get("SHYFT_TOKEN")
        or os.environ.get("X_TOKEN")
        or ""
    ).strip()


def region() -> str:
    return os.environ.get("SHYFT_REGION") or "fra"
