#!/usr/bin/env python3
"""Read-only: dump first complete data-shred batch from a FEEDCAP1 file."""
import struct
import sys

DATA = {0xA0, 0x80, 0x90, 0xB0}


def main():
    path = sys.argv[1]
    want = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    with open(path, "rb") as f:
        hdr = f.read(40)
        assert hdr[:8] == b"FEEDCAP1"
        seen = {}
        shown = 0
        while shown < want:
            rec = f.read(24)
            if len(rec) < 24:
                break
            rx_ns, rx_tsc, ln, seq = struct.unpack("<QQII", rec)
            payload = f.read(ln)
            if len(payload) < ln or ln < 88:
                continue
            typ = payload[64]
            if (typ & 0xF0) not in DATA:
                continue
            slot = struct.unpack_from("<Q", payload, 65)[0]
            index = struct.unpack_from("<I", payload, 73)[0]
            fec = struct.unpack_from("<I", payload, 79)[0]
            flags = payload[85]
            size = struct.unpack_from("<H", payload, 86)[0]
            key = slot
            seen.setdefault(key, []).append(
                (index, typ, flags, size, ln, fec, payload)
            )
            if flags & 0x80:
                recs = sorted(seen[key], key=lambda x: x[0])
                print(
                    "slot %d n=%d complete_idx=%d variant=0x%02x size=%d len=%d fec=%d"
                    % (slot, len(recs), index, typ, size, ln, fec)
                )
                for i, (idx, t, fl, sz, ln_, fc, p) in enumerate(recs[:6]):
                    pay = p[88:88 + min(32, max(0, sz - 88))]
                    print(
                        "  i=%d idx=%d var=0x%02x fl=0x%02x size=%d len=%d fec=%d head=%s"
                        % (i, idx, t, fl, sz, ln_, fc, pay.hex())
                    )
                # concat using size-88
                buf = bytearray()
                for idx, t, fl, sz, ln_, fc, p in recs:
                    if sz >= 88 and sz <= ln_:
                        buf += p[88:sz]
                print("concat_len", len(buf), "first64", bytes(buf[:64]).hex())
                if len(buf) >= 48:
                    nh, hsh, ntx = struct.unpack_from("<Q32sQ", buf, 0)
                    print("as_entry num_hashes=%d ntx=%d hash=%s" % (nh, ntx, hsh.hex()))
                shown += 1
                seen.clear()


if __name__ == "__main__":
    main()
