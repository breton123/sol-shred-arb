#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROTO="${HERE}/proto"
GEN="${HERE}/gen"
mkdir -p "${PROTO}" "${GEN}"
curl -fsSL -o "${PROTO}/geyser.proto" \
  "https://raw.githubusercontent.com/rpcpool/yellowstone-grpc/master/yellowstone-grpc-proto/proto/geyser.proto"
curl -fsSL -o "${PROTO}/solana-storage.proto" \
  "https://raw.githubusercontent.com/rpcpool/yellowstone-grpc/master/yellowstone-grpc-proto/proto/solana-storage.proto"
python3 -m grpc_tools.protoc \
  -I "${PROTO}" \
  --python_out="${GEN}" \
  --grpc_python_out="${GEN}" \
  "${PROTO}/geyser.proto" \
  "${PROTO}/solana-storage.proto"
: > "${GEN}/__init__.py"
python3 -c "import sys; sys.path.insert(0,'${GEN}'); import geyser_pb2, geyser_pb2_grpc; print('proto ok')"
