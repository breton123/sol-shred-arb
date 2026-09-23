#!/usr/bin/env bash
# Run bench_nic002.sh inside a private user+net+mount namespace.
# Safe to remount /run here: it is not the host mount namespace.
set -euo pipefail

if [[ "$(readlink /proc/1/ns/mnt 2>/dev/null || true)" == "$(readlink /proc/self/ns/mnt)" ]]; then
    echo "run_unshare.sh: invoke via:" >&2
    echo "  unshare --user --map-root-user --mount --net -- $0" >&2
    exit 1
fi

mount -t tmpfs tmpfs /run
mkdir -p /run/netns
if [[ -d /var/run && ! -L /var/run ]]; then
    mount --bind /run /var/run || true
fi

exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bench_nic002.sh" "$@"
