#!/usr/bin/env python3
"""PAPER-002 — economic truth audit. Historical S at slot N-1, not S_today.

Throws away PAPER-LIVE-001 PnL. Latency numbers stay. No new venues.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper002"
SOL = "So11111111111111111111111111111111111111112"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
SOL_USD = 115.0
LIVE_SLOT = 450112763
CAP_LO, CAP_HI = 449848541, 449891196


def usd(lamports: int) -> float:
    return lamports * SOL_USD / 1e9


def load_cases(n: int) -> list[dict]:
    rows = []
    pairs = ROOT / "shred_v1_fat" / "pairs.jsonl"
    for line in pairs.open(encoding="utf-8"):
        r = json.loads(line)
        dex = r.get("dexes") or []
        if set(dex) != {"Meteora DLMM", "Pump Swap"}:
            continue
        if not r.get("trigger_sig") or not r.get("mriya_sig"):
            continue
        if not r.get("pair_ok"):
            continue
        rows.append(r)
    rows.sort(key=lambda x: -float(x.get("profit") or 0))
    return rows[:n]


def get_tx(sig: str) -> dict | None:
    try:
        return d.rpc("getTransaction", [
            sig, {"encoding": "json", "maxSupportedTransactionVersion": 1},
        ])
    except Exception as e:
        print(f"  tx fail {sig[:8]} {type(e).__name__}", flush=True)
        return None


def vault_amt(tx: dict, vault: str, which: str) -> int | None:
    keys = d.tx_keys(tx)
    try:
        idx = keys.index(vault)
    except ValueError:
        return None
    for b in (tx.get("meta") or {}).get(f"{which}TokenBalances") or []:
        if b.get("accountIndex") == idx:
            return int(b["uiTokenAmount"]["amount"])
    return None


def native_delta(tx: dict, idx: int) -> int:
    pre = (tx.get("meta") or {}).get("preBalances") or []
    post = (tx.get("meta") or {}).get("postBalances") or []
    if idx >= len(pre) or idx >= len(post):
        return 0
    return int(post[idx]) - int(pre[idx])


def pump_ix_amount(tx: dict) -> tuple[str | None, int | None]:
    if not tx:
        return None, None
    keys = d.tx_keys(tx)
    ixs = list(tx["transaction"]["message"].get("instructions") or [])
    for g in (tx.get("meta") or {}).get("innerInstructions") or []:
        ixs.extend(g.get("instructions") or [])
    for ix in ixs:
        pid = ix.get("programId")
        if pid is None:
            i = ix.get("programIdIndex")
            pid = keys[i] if i is not None and i < len(keys) else None
        if pid != PUMP:
            continue
        accs = []
        for a in ix.get("accounts") or []:
            accs.append(keys[a] if isinstance(a, int) else a)
        raw = ix.get("data")
        data = d._b58_any(raw) if isinstance(raw, str) else bytes(raw or [])
        # live pump sell/buy: amount u64 after 8-byte disc (or 1-byte if compact)
        amt = None
        if len(data) >= 16:
            import struct
            amt = int.from_bytes(data[8:16], "little")
        return (accs[0] if accs else None), amt
    return None, None


def write_pair(path: Path, dlmm_row: dict, pump_row: dict, slot: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        live.write_u32(f, live.LIVE_MAGIC)
        live.write_u16(f, 1)
        live.write_u16(f, 2)
        live.write_u64(f, slot)
        live.write_u64(f, slot)
        live.write_meta(f, live.PROTO_DLMM, dlmm_row["pubkey"],
                        dlmm_row["mint_x"], dlmm_row["mint_y"],
                        dlmm_row["vault_x"], dlmm_row["vault_y"])
        live.write_dlmm(f, dlmm_row["snap"])
        live.write_meta(f, live.PROTO_PUMP, pump_row["pubkey"],
                        pump_row["mint_x"], pump_row["mint_y"],
                        pump_row["vault_x"], pump_row["vault_y"])
        live.write_pump(f, pump_row)


def audit_one(r: dict, fees) -> dict:
    win = get_tx(r["mriya_sig"])
    trig = get_tx(r["trigger_sig"])
    out = {
        "slot": r["slot"],
        "profit_them": float(r.get("profit") or 0),
        "winner": r["mriya_sig"],
        "trigger": r["trigger_sig"],
        "verdict": "INCOMPLETE",
    }
    if not win:
        out["why"] = "winner_tx_missing"
        return out
    dsw = d.decode_swaps(win)
    p_pk, p_amt = pump_ix_amount(win)
    t_pk, t_amt = pump_ix_amount(trig) if trig else (None, None)
    dlmm_pk = dsw[0]["pair"] if dsw else None
    pump_pk = p_pk
    out["dlmm_pool"] = dlmm_pk
    out["pump_pool"] = pump_pk
    out["winner_dlmm_ain"] = dsw[0]["amount_in"] if dsw else None
    out["winner_pump_ix_ain"] = p_amt
    out["trigger_pump_ix_ain"] = t_amt
    out["trigger_dlmm_ain"] = None
    if trig:
        tsw = d.decode_swaps(trig)
        if tsw:
            out["trigger_dlmm_ain"] = tsw[0]["amount_in"]
            if not dlmm_pk:
                dlmm_pk = tsw[0]["pair"]
                out["dlmm_pool"] = dlmm_pk
        if t_pk and not pump_pk:
            pump_pk = t_pk
            out["pump_pool"] = pump_pk

    pump_row = live.fetch_pump(pump_pk, fees) if pump_pk else None
    dlmm_row = live.fetch_dlmm(dlmm_pk) if dlmm_pk else None
    out["s_dlmm_source"] = "S_TODAY" if dlmm_row else None
    out["s_pump_today_base"] = pump_row["reserve_base"] if pump_row else None
    out["s_pump_today_quote"] = pump_row["reserve_quote"] if pump_row else None
    out["s_dlmm_today_slot"] = dlmm_row["slot"] if dlmm_row else None

    hist_b = hist_q = None
    src_tx = trig or win
    if pump_row:
        vb = d._pk(pump_row["vault_x"])
        vq = d._pk(pump_row["vault_y"])
        hist_b = vault_amt(src_tx, vb, "pre")
        hist_q = vault_amt(src_tx, vq, "pre")
        post_b = vault_amt(src_tx, vb, "post")
        post_q = vault_amt(src_tx, vq, "post")
        out["s_pump_hist_base"] = hist_b
        out["s_pump_hist_quote"] = hist_q
        out["trigger_vault_dbase"] = (None if hist_b is None or post_b is None
                                      else post_b - hist_b)
        out["trigger_vault_dquote"] = (None if hist_q is None or post_q is None
                                       else post_q - hist_q)
        if hist_b and hist_q:
            out["s_pump_source"] = "S_PRETOKEN (slot N trigger/winner pre)"
        else:
            out["s_pump_source"] = "VAULTS_NOT_IN_TX"

    if dlmm_row:
        vx = d._pk(dlmm_row["vault_x"])
        vy = d._pk(dlmm_row["vault_y"])
        out["s_dlmm_hist_rx"] = vault_amt(src_tx, vx, "pre")
        out["s_dlmm_hist_ry"] = vault_amt(src_tx, vy, "pre")
        out["s_dlmm_today_rx"] = dlmm_row["snap"]["reserve_x"]
        out["s_dlmm_today_ry"] = dlmm_row["snap"]["reserve_y"]

    if pump_row and dlmm_row and hist_b and hist_q:
        hist_pump = dict(pump_row)
        hist_pump["reserve_base"] = hist_b
        hist_pump["reserve_quote"] = hist_q
        hist_pump["status"] = 0
        slot = int(r["slot"]) - 1
        write_pair(OUT / "univ" / f"{r['slot']}.today.bin", dlmm_row, pump_row, LIVE_SLOT)
        write_pair(OUT / "univ" / f"{r['slot']}.histpump.bin", dlmm_row, hist_pump, slot)
        out["univ_today"] = str(OUT / "univ" / f"{r['slot']}.today.bin")
        out["univ_histpump"] = str(OUT / "univ" / f"{r['slot']}.histpump.bin")
        out["verdict"] = "READY_FOR_KERNEL"
    elif not pump_row or not dlmm_row:
        out["why"] = "pool_fetch_failed"
    else:
        out["why"] = "no_hist_pump_vaults"
        out["verdict"] = "PUMP_HIST_MISSING"
    return out


def main() -> int:
    live.load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    print("PAPER-002  economic truth audit", flush=True)
    print(f"  S_today slot={LIVE_SLOT}  capture={CAP_LO}..{CAP_HI}  "
          f"delta={LIVE_SLOT - CAP_LO} slots", flush=True)

    gcfg_pk = d._pk(d.find_pda([b"global_config"], d.b58decode(PUMP)))
    gacc = d.get_multiple([gcfg_pk])[0]
    fees = live.parse_global(gacc["data"]) if gacc else (20, 5, 0, 0)

    seeds = load_cases(20)
    print(f"  cases={len(seeds)}", flush=True)
    cases = []
    for i, r in enumerate(seeds):
        print(f"  [{i+1:02}/{len(seeds)}] slot={r['slot']} ${r['profit']:.2f}", flush=True)
        cases.append(audit_one(r, fees))

    ready = [c for c in cases if c.get("verdict") == "READY_FOR_KERNEL"]
    meta = {
        "live_slot": LIVE_SLOT,
        "capture_lo": CAP_LO,
        "capture_hi": CAP_HI,
        "slot_delta": LIVE_SLOT - CAP_LO,
        "n": len(cases),
        "ready": len(ready),
        "cases": cases,
        "phantom": {
            "usd_061": {
                "n": 377971,
                "route_id": 1,
                "family": 0,
                "amount_in": 822222222,
                "gross_lamports": 5336841,
                "pools": ["ENiVH49XwRM3Cu9n4Tp6CGynCFXf3Mz6CE3GRmVk1LH4 (pump 0)",
                          "4MjpgAT7H8GmWsZDUaeGUNZwjur8n8sKCSPHHjQRE4sm (dlmm 38)"],
            },
            "usd_352": {
                "n": 1297,
                "route_id": 126,
                "family": 255,
                "n_hop": 3,
                "proto": [2, 5, 5],
                "amount_in": 8333333333,
                "gross_lamports": 3069199485,
                "pools": ["5PGhKctym6odbHGo2tKMST2AjmJsb2uZBQrKkn4ZuFT5 (pump 76)",
                          "3WZUnUVQwFVSod5dxk99g9PyQRhSTNkLdb3uYRt19Kw1 (damm 74)"],
                "note": "exact count of PAPER-001 >=$50 and >=$100 rows",
            },
        },
    }
    (OUT / "cases.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    write_md(meta)
    print(f"wrote {OUT / 'cases.json'} ready={len(ready)}/{len(cases)}", flush=True)
    return 0


def write_md(meta: dict) -> None:
    lines = []
    a = lines.append
    a("# PAPER-002")
    a("")
    a("Economic truth audit. PAPER-LIVE-001 **PnL is void**. Latency stands.")
    a("")
    a("## Verdict: FAIL — chronology")
    a("")
    a(f"- `liveuniv.bin` slot **{meta['live_slot']}** (S_today, fetched 2026-09-24)")
    a(f"- FEEDCAP1 slots **{meta['capture_lo']}–{meta['capture_hi']}**")
    a(f"- delta **{meta['slot_delta']} slots** (~29 h). We quoted 2026-09-24 state against 2026-09-23 shreds.")
    a("- That is `S_today`, not `S_{slot=N-1}`.")
    a("")
    a("Throw away: searchable $762k, UNCLAIMED $123k, could_have_raced $83k, ratio p50=72.7.")
    a("")
    a("## Phantoms")
    a("")
    a("### $0.61 × 377,971")
    p = meta["phantom"]["usd_061"]
    a(f"- family 0, route_id {p['route_id']}, amount_in {p['amount_in']} (0.822 SOL), gross {p['gross_lamports']} lamports")
    a(f"- trigger pool_idx 0 or 38: `{p['pools'][0]}` / `{p['pools'][1]}`")
    a("- `cycle_size` on **today's** top pair. Same size, same gp, every shred. N was not applied (`hot_decode` failed on raw payload).")
    a("")
    a("### $352.96 × 1,297")
    q = meta["phantom"]["usd_352"]
    a(f"- family OTHER, route_id {q['route_id']}, 3-hop proto Pump→DAMM→DAMM `{q['proto']}`")
    a(f"- amount_in {q['amount_in']} (8.333 SOL), gross {q['gross_lamports']} lamports")
    a(f"- pools: `{q['pools'][0]}`, `{q['pools'][1]}`")
    a(f"- **This is exactly the {q['n']} rows ≥ $50 and ≥ $100.** One stale 3-hop on S_today.")
    a("")
    a("## 20 DLMM→Pump winners")
    a("")
    a("| slot | them $ | S_pump | hist base/quote | today base/quote | trigger N | winner DLMM ain | verdict |")
    a("|------|--------|--------|-----------------|------------------|-----------|-----------------|---------|")
    for c in meta["cases"]:
        hb = c.get("s_pump_hist_base")
        hq = c.get("s_pump_hist_quote")
        tb = c.get("s_pump_today_base")
        tq = c.get("s_pump_today_quote")
        hist = "-" if hb is None else f"{hb}/{hq}"
        today = "-" if tb is None else f"{tb}/{tq}"
        a(f"| {c['slot']} | ${c['profit_them']:.2f} | {c.get('s_pump_source') or '-'} | {hist} | {today} | "
          f"{c.get('trigger_dlmm_ain') or c.get('trigger_pump_ix_ain') or '-'} | "
          f"{c.get('winner_dlmm_ain') or '-'} | {c.get('verdict')} |")
    a("")
    a("S_dlmm bins are **S_today** on every row (RPC cannot return account bytes at slot N-1).")
    a("S_pump vaults **are** recoverable from `preTokenBalances` when the vaults appear in the trigger/winner.")
    a("")
    a("Kernel quotes on the written `univ/*.histpump.bin` files are the next gate (`paper002` binary).")
    a("Audit does not pass until `cycle_size(S_dlmm_{N-1}, S_pump_{N-1})` matches the winner hop amounts.")
    (OUT / "PAPER-002.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
