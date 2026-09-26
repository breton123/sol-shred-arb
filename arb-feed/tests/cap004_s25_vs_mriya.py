#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

S25H = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004_s25\cap004_hits.jsonl")
S25P = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004_s25\pairs.jsonl")
MH = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004\cap004_hits.jsonl")
MP = Path(r"c:\Users\louis\Desktop\TheMoneyMaker\arb-cap\cap004\pairs.jsonl")
LOCAL = 20.0
SHORT = {
    "DtvmxrTACskMG2W8a6KXgSemUfvyNVeQTgfpJoGvMVKx": "Dtvmxr",
    "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu": "7dGrdJ",
    "4BQ6ATUt26GFdiYQfht23iwfKyYD9D7XbL5ATqNGk3xK": "4BQ6AT",
    "gtagyESa99t49VmUqnnfsuowYnigSNKuYXdXWyXWNdd": "gtagyE",
    "9EwQoN74Hzw747EM7wB3WtvgAdRGH1czaPtbqZj1qDj4": "9EwQoN",
}


def dt_us(later, earlier):
    if later is None or earlier is None or later == 0 or earlier == 0:
        return None
    return (int(later) - int(earlier)) / 1000.0


def load(hits_p, pairs_p, default_user=None):
    meta = {}
    for line in pairs_p.read_text(encoding="utf-8").splitlines():
        p = json.loads(line)
        meta[p.get("mriya_sig")] = p
    rows = []
    for line in hits_p.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        p = meta.get(r.get("mriya_sig")) or {}
        r["user"] = p.get("user") or default_user
        r["profit"] = float(p.get("profit") or 0)
        r["dexes"] = tuple(p.get("dexes") or [])
        rows.append(r)
    return rows


srows = load(S25H, S25P)
mrows = load(MH, MP, "Mriya")
mriya_by_slot = defaultdict(list)
for r in mrows:
    if r.get("mriya_found"):
        mriya_by_slot[int(r["slot"])].append(r)

pos = []
for r in srows:
    if not (r.get("mriya_found") and r.get("trig_found") and r.get("act_found")):
        continue
    a = dt_us(r.get("mriya_rx0"), r.get("act_rx"))
    if a is None or a < LOCAL:
        continue
    slot = int(r["slot"])
    ms = mriya_by_slot.get(slot) or []
    m_imm = any(m.get("immediate") and m.get("pair_ok") for m in ms)
    m_any = bool(ms)
    pos.append((a, r.get("profit") or 0, r.get("user"), r.get("dist"), m_any, m_imm, slot, r.get("dexes")))

print("positive-budget vs Mriya occupancy")
print(f"n={len(pos)}")

def dump(title, xs):
    print(f"\n{title}  n={len(xs)} profit={sum(p for _,p,_,_,_,_,_,_ in xs):.1f}")
    by = defaultdict(lambda: [0, 0.0])
    for a, p, u, d, *_ in xs:
        by[u][0] += 1
        by[u][1] += p
    for u, short in SHORT.items():
        n, pr = by[u]
        if n:
            print(f"  {short:<8} {n:5} {pr:10.1f}")

dump("ALL pos budget", pos)
dump("Mriya also in slot (any)", [x for x in pos if x[4]])
dump("Mriya immediate in slot", [x for x in pos if x[5]])
dump("NO Mriya in slot", [x for x in pos if not x[4]])
dump("NO Mriya + dist<=2", [x for x in pos if not x[4] and x[3] is not None and int(x[3]) <= 2])
dump("NO Mriya + dist>=6", [x for x in pos if not x[4] and x[3] is not None and int(x[3]) >= 6])

# Mriya vs this searcher RX if both located
print("\nWhen Mriya also located in slot: T_searcher - T_Mriya (us) on pos-budget races")
dels = []
for r in srows:
    if not (r.get("mriya_found") and r.get("act_found")):
        continue
    a = dt_us(r.get("mriya_rx0"), r.get("act_rx"))
    if a is None or a < LOCAL:
        continue
    ms = mriya_by_slot.get(int(r["slot"])) or []
    both = [m for m in ms if m.get("mriya_found")]
    if not both:
        continue
    # earliest Mriya first shred in slot
    t_m = min(int(m["mriya_rx0"]) for m in both if m.get("mriya_rx0"))
    t_s = int(r["mriya_rx0"])
    dels.append((t_s - t_m) / 1000.0)
if dels:
    dels.sort()
    def q(p):
        i = int(round((p / 100.0) * (len(dels) - 1)))
        return dels[max(0, min(i, len(dels) - 1))]
    print(f"n={len(dels)} p10={q(10):.1f} p50={q(50):.1f} p90={q(90):.1f} later_than_mriya={sum(1 for d in dels if d>0)}/{len(dels)}")
