#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import live001 as live  # noqa: E402
import live002 as l  # noqa: E402
import record_dlmm as d  # noqa: E402

live.load_dotenv()
c = json.loads((Path(__file__).resolve().parent / "candidates.json").read_text(encoding="utf-8"))
cp = [k for k, v in c.items() if v["pid"] == l.CPMM]
accs = d.get_multiple(cp)
print("fetched", len(cp))
ok = 0
for pk, a in zip(cp, accs):
    if a is None or a.get("owner") != l.CPMM:
        continue
    data = a["data"]
    if not (500 <= len(data) <= 900):
        continue
    p = l.parse_cpmm(data)
    if p is None or not l.looks_like_pool("cpmm", data, p):
        print("reject", pk[:8], "len", len(data))
        continue
    vx, vy = d._pk(p["vault_x"]), d._pk(p["vault_y"])
    vs = d.get_multiple([vx, vy])
    rx = d.token_amount(vs[0]["data"]) if vs[0] else 0
    ry = d.token_amount(vs[1]["data"]) if vs[1] else 0
    mx, my = d._pk(p["mint_x"]), d._pk(p["mint_y"])
    print(
        f"{pk[:8]} len={len(data)} rx={rx} ry={ry} {mx[:6]}/{my[:6]} usd={c[pk]['usd']:.0f}"
    )
    if rx and ry:
        ok += 1
print("both-reserve", ok)
