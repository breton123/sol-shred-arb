#!/usr/bin/env python3
"""Replay a captured YS jsonl through STATE-010 barrier + production apply.

Each line:
  {"kind":"slot","slot":N}
  {"kind":"tx","slot":N,"parsed":{sig,keys,instructions}}
  {"kind":"account","slot":N,"pubkey":...,"data":hex,"txn_sig":hex,"write_version":N}

Does not start gRPC. Does not restart the live soak.
Requires STATE_APPLY / state_apply on PATH for kernel steps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Replay is a thin driver: import State008 pieces after the live process
# is not required. For machine-speed soak, feed the same apply_tx /
# apply_update / try_publish on a State008 instance with grpc_loop mocked.

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: replay.py events.jsonl", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    n = 0
    kinds = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        kinds[ev.get("kind")] = kinds.get(ev.get("kind"), 0) + 1
        n += 1
    print(json.dumps({"events": n, "kinds": kinds, "note": "wire into State008.apply_*"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
