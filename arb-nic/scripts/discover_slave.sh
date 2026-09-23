#!/usr/bin/env bash
# Watch which LACP slave eats UDP/39001 from the home sender.
# Bind the dest port so we can also count in userspace. No XDP.
# Does not need root (sysfs + UDP bind).
set -euo pipefail

PORT=${PORT:-39001}
WAIT=${WAIT:-20}

python3 - "${PORT}" "${WAIT}" <<'PY'
import socket, sys, time, os

port = int(sys.argv[1])
wait = float(sys.argv[2])

def snap():
    out = {}
    for n in ("eno1np0", "eno2np1", "bond0"):
        with open(f"/sys/class/net/{n}/statistics/rx_packets") as f:
            pk = int(f.read())
        with open(f"/sys/class/net/{n}/statistics/rx_bytes") as f:
            by = int(f.read())
        out[n] = (pk, by)
    return out

def qstats(dev):
    import re, subprocess
    out = subprocess.check_output(["ethtool", "-S", dev], text=True, stderr=subprocess.DEVNULL)
    d = {}
    for line in out.splitlines():
        m = re.match(r"\s*rx-(\d+)\.packets:\s*(\d+)", line)
        if m:
            d[int(m.group(1))] = int(m.group(2))
    return d

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", port))
s.settimeout(0.2)

print(f"discover_slave: listening 0.0.0.0:{port} for {wait:.0f}s", flush=True)
print("discover_slave: from WSL run  COUNT=20000 RATE=5000 ./scripts/send_nic005.sh", flush=True)

before = snap()
q1, q2 = qstats("eno1np0"), qstats("eno2np1")
got = 0
src = None
end = time.time() + wait
while time.time() < end:
    try:
        data, addr = s.recvfrom(2048)
        got += 1
        if src is None:
            src = addr
            print(f"discover_slave: first packet from {addr[0]}:{addr[1]}  ({len(data)} B)", flush=True)
    except socket.timeout:
        pass
after = snap()
q1b, q2b = qstats("eno1np0"), qstats("eno2np1")
s.close()

print()
print(f"userspace:  {got} datagrams on :{port}")
if src:
    print(f"on-wire:    {src[0]}:{src[1]}  →  195.242.152.178:{port}")
print()
print(f"{'iface':<12} {'+pkts':>10} {'+bytes':>12}")
winner = None
best = -1
for n in ("eno1np0", "eno2np1", "bond0"):
    dp = after[n][0] - before[n][0]
    db = after[n][1] - before[n][1]
    print(f"{n:<12} {dp:10d} {db:12d}")
    if n != "bond0" and dp > best:
        best = dp
        winner = n

print()
if got == 0:
    print("discover_slave: no userspace hits — send from WSL while this is running")
    sys.exit(2)
if winner is None or best < got // 2:
    print("discover_slave: slave counters did not track the flow; rerun with a larger COUNT")
    sys.exit(3)
print()
qwin, qbest = None, -1
for label, a, b in (("eno1np0", q1, q1b), ("eno2np1", q2, q2b)):
    deltas = [(q, b.get(q, 0) - a.get(q, 0)) for q in b]
    hot = [(q, d) for q, d in deltas if d > 0]
    hot.sort(key=lambda x: -x[1])
    if hot:
        print(f"{label} queues: " + " ".join(f"q{q}+{d}" for q, d in hot[:8]))
        if hot[0][1] > qbest:
            qbest = hot[0][1]
            qwin = hot[0][0]
print()
print(f"attach XDP on:  {winner}")
if qwin is not None:
    print(f"RSS queue:      {qwin}  (without ntuple)")
print(f"then:  sudo DEV={winner} MODE=copy COUNT=1000000 ./scripts/bench_nic005.sh")
print(f"ntuple loc 6 steers dest-port {port} → q0. If that fails: QUEUE={qwin if qwin is not None else 13}")
PY
