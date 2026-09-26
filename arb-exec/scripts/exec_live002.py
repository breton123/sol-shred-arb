#!/usr/bin/env python3
"""EXEC-LIVE-002 — bake live accounts into the frozen route0 template, sign, simulate.

Does not send the arb. Does not mutate route0.h / tx_template.c.
Never prints secrets.
"""

from __future__ import annotations

import json
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

from solders.keypair import Keypair

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / ".deploy"
OUT = ROOT.parent / "arb-cap" / "exec_live002"

DLMM = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"
PUMP = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
PAIR_DLMM = "DAErPzgiYQDhDwpMRgdvikXaZmnmznc3du3jy9i1AABk"
PAIR_PUMP = "BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs"
SOL = "So11111111111111111111111111111111111111112"
TOKENKEG = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SYSTEM = "11111111111111111111111111111111"
ATA_PROG = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
MEMO = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
FEE_PROG = "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ"
CU_PROG = "ComputeBudget111111111111111111111111111111"

NAMES = [
    "authority", "user_quote", "user_base", "token_program", "system_program",
    "ata_program", "memo_program", "dlmm_program", "dlmm_event_auth",
    "dlmm_lb_pair", "dlmm_bitmap", "dlmm_reserve_x", "dlmm_reserve_y",
    "dlmm_oracle", "dlmm_host_fee", "dlmm_token_x_mint", "dlmm_token_y_mint",
    "dlmm_bin_0", "dlmm_bin_1", "pump_program", "pump_event_auth", "pump_pool",
    "pump_global", "pump_fee_config", "pump_fee_program", "pump_base_mint",
    "pump_quote_mint", "pump_pool_base", "pump_pool_quote", "pump_proto_fee",
    "pump_proto_fee_ata", "pump_creator_ata", "pump_creator_auth",
    "pump_global_vol", "pump_user_vol",
]

ACC_SIGNER = [1] + [0] * 34
ACC_WRITE = [
    1, 1, 1, 0, 0, 0, 0, 0, 0,
    1, 0, 1, 1, 1, 0, 0, 0,
    1, 1, 0, 0,
    1, 0, 0, 0, 0, 0,
    1, 1, 0, 1, 1, 0, 0, 1,
]

TX_NKEYS = 35
TX_LEN = 1305
N_RO_UNSIGNED = 20
OFF_SIG = 1
OFF_MSG = 65
MSG_LEN = 1240
OFF_BLOCKHASH = 1189
OFF_CU_PRICE = 1234
OFF_DIRECTION = 1288
OFF_AMOUNT_IN = 1289
OFF_MIN_PROFIT = 1297
OFF_NKEYS = 68
OFF_KEYS = 69
CU_LIMIT = 400000
TINY_IN = 10_000
MIN_PROFIT = 1
DISC = b"ARBEXEC0"


def b58_any(s: str) -> bytes:
    alph = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = 0
    for c in s:
        n = n * 58 + alph.index(c)
    pad = 0
    for c in s:
        if c == "1":
            pad += 1
        else:
            break
    h = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\x00" * pad + h


def payer_kp() -> Keypair:
    secret = b58_any(os.environ["PRIVATE_KEY"].strip())
    if len(secret) == 64:
        return Keypair.from_bytes(secret)
    if len(secret) == 32:
        return Keypair.from_seed(secret)
    raise SystemExit(f"PRIVATE_KEY length {len(secret)}")


def ata(owner: str, mint: str, token_program: str) -> str:
    return d._pk(
        d.find_pda(
            [d.b58decode(owner), d.b58decode(token_program), d.b58decode(mint)],
            d.b58decode(ATA_PROG),
        )
    )


def program_v3() -> str:
    DEPLOY.mkdir(parents=True, exist_ok=True)
    path = DEPLOY / "program-v3.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return d._pk(bytes(raw[32:64]))
    kp = Keypair()
    path.write_text(json.dumps(list(bytes(kp))) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return str(kp.pubkey())


def ix_accounts(ix: dict, keys: list[str]) -> list[str]:
    out = []
    for a in ix.get("accounts") or []:
        out.append(keys[a] if isinstance(a, int) else a)
    return out


def ix_program(ix: dict, keys: list[str]) -> str | None:
    pid = ix.get("programId")
    if pid is not None:
        return pid
    idx = ix.get("programIdIndex")
    if idx is not None and idx < len(keys):
        return keys[idx]
    return None


def latest_pump_metas() -> dict:
    """Copy static Pump accounts from a recent successful sell/buy on this pool."""
    sigs = d.rpc("getSignaturesForAddress", [PAIR_PUMP, {"limit": 12}])
    for s in sigs:
        tx = d.rpc(
            "getTransaction",
            [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}],
        )
        if not tx or (tx.get("meta") or {}).get("err"):
            continue
        keys = d.tx_keys(tx)
        ixs = list(tx["transaction"]["message"].get("instructions") or [])
        for g in (tx.get("meta") or {}).get("innerInstructions") or []:
            ixs.extend(g.get("instructions") or [])
        for ix in ixs:
            if ix_program(ix, keys) != PUMP:
                continue
            accs = ix_accounts(ix, keys)
            raw = ix.get("data")
            data = d._b58_any(raw) if isinstance(raw, str) else bytes(raw or [])
            if len(accs) < 22 or len(data) < 16:
                continue
            if accs[0] != PAIR_PUMP:
                continue
            return {
                "nacc": len(accs),
                "disc": data[:8].hex(),
                "global": accs[2],
                "proto_fee": accs[9],
                "proto_fee_ata": accs[10],
                "event": accs[15],
                "creator_ata": accs[17],
                "creator_auth": accs[18],
                "slot19": accs[19] if len(accs) > 19 else None,
                "fee_program": accs[20] if len(accs) > 21 else FEE_PROG,
                "fee_config": accs[21] if len(accs) > 21 else accs[19],
            }
    raise SystemExit("no recent Pump ix on the live pool")


def resolve(wallet: str) -> list[str]:
    sn = d.snapshot_pool(PAIR_DLMM, [PAIR_DLMM], None)
    if not sn or not sn.get("lb"):
        raise SystemExit("DLMM snapshot failed")
    lb = sn["lb"]
    mint_x = d._pk(lb["token_x"])
    mint_y = d._pk(lb["token_y"])
    bins = [d.bin_array_pda(PAIR_DLMM, i) for i in d.array_indexes(lb["active_id"])]
    if len(bins) < 2:
        bins = bins + [bins[0]]
    oracle = d._pk(d.find_pda([b"oracle", d.b58decode(PAIR_DLMM)], d.b58decode(DLMM)))
    bitmap = d._pk(d.find_pda([b"bitmap", d.b58decode(PAIR_DLMM)], d.b58decode(DLMM)))
    host = d._pk(d.find_pda([b"host_fee", d.b58decode(PAIR_DLMM)], d.b58decode(DLMM)))
    event_dlmm = d._pk(d.find_pda([b"__event_authority"], d.b58decode(DLMM)))
    pacc = d.get_multiple([PAIR_PUMP])[0]
    p = live.parse_pump_pool(pacc["data"]) if pacc else None
    if not p:
        raise SystemExit("pump parse failed")
    pump = latest_pump_metas()
    gvol = d._pk(d.find_pda([b"global_volume_accumulator"], d.b58decode(PUMP)))
    uvol = d._pk(d.find_pda([b"user_volume_accumulator", d.b58decode(wallet)], d.b58decode(PUMP)))
    if pump.get("slot19") and pump["slot19"] != pump.get("fee_config"):
        gvol = pump["slot19"]
    keys = [
        wallet,
        ata(wallet, SOL, TOKENKEG),
        ata(wallet, mint_x, TOKEN2022),
        TOKENKEG,
        SYSTEM,
        ATA_PROG,
        MEMO,
        DLMM,
        event_dlmm,
        PAIR_DLMM,
        bitmap,
        d._pk(lb["vault_x"]),
        d._pk(lb["vault_y"]),
        oracle,
        host,
        mint_x,
        mint_y,
        bins[0],
        bins[1],
        PUMP,
        pump["event"],
        PAIR_PUMP,
        pump["global"],
        pump["fee_config"],
        pump["fee_program"],
        mint_x,
        mint_y,
        d._pk(p["vault_base"]),
        d._pk(p["vault_quote"]),
        pump["proto_fee"],
        pump["proto_fee_ata"],
        pump["creator_ata"],
        pump["creator_auth"],
        gvol,
        uvol,
    ]
    return keys


def collisions(keys: list[str]) -> list[str]:
    seen: dict[str, list[int]] = {}
    for i, k in enumerate(keys):
        seen.setdefault(k, []).append(i)
    allowed = {
        frozenset({15, 25}),
        frozenset({16, 26}),
    }
    bad = []
    for k, idxs in seen.items():
        if len(idxs) < 2:
            continue
        if frozenset(idxs) in allowed:
            continue
        bad.append(f"{[NAMES[i] for i in idxs]} -> {k[:8]}..")
    return bad


def compact_u16(n: int) -> bytes:
    if n >= 128:
        raise ValueError("compact u16")
    return bytes([n])


def compile_template(keys: list[str], our_exec: str) -> bytes:
    raw = [d.b58decode(k) for k in keys]
    exec_b = d.b58decode(our_exec)
    cu_b = d.b58decode(CU_PROG)
    if raw[25] != raw[15] or raw[26] != raw[16]:
        raise SystemExit("mint alias lock failed")
    uniq: list[bytes] = []
    mapping = [0] * 35

    def add(pk: bytes) -> int:
        for i, u in enumerate(uniq):
            if u == pk:
                return i
        if len(uniq) >= TX_NKEYS:
            raise SystemExit("too many unique keys")
        uniq.append(pk)
        return len(uniq) - 1

    def want(signer: int, writable: int, pass_: int) -> bool:
        if pass_ == 0:
            return bool(signer and writable)
        if pass_ == 1:
            return bool(signer and not writable)
        if pass_ == 2:
            return bool((not signer) and writable)
        return bool((not signer) and (not writable))

    n_writable = 0
    exec_idx = 0
    cu_idx = 0
    for pass_ in range(4):
        for i in range(35):
            if not want(ACC_SIGNER[i], ACC_WRITE[i], pass_):
                continue
            mapping[i] = add(raw[i])
        if pass_ == 2:
            n_writable = len(uniq)
        if pass_ == 3:
            exec_idx = add(exec_b)
            cu_idx = add(cu_b)
    if len(uniq) != TX_NKEYS:
        raise SystemExit(f"unique keys {len(uniq)} != {TX_NKEYS}")
    if n_writable != 15:
        raise SystemExit(f"writable unique {n_writable} != 15")
    if len(uniq) - n_writable != N_RO_UNSIGNED:
        raise SystemExit("readonly unique mismatch")

    ixdata = DISC + bytes([0]) + struct.pack("<QQ", 0, 0)
    out = bytearray()
    out += compact_u16(1)
    out += bytes(64)
    out += bytes([1, 0, N_RO_UNSIGNED])
    out += compact_u16(TX_NKEYS)
    if len(out) != OFF_KEYS:
        raise SystemExit(f"keys offset {len(out)} != {OFF_KEYS}")
    for u in uniq:
        out += u
    out += bytes(32)
    out += compact_u16(3)
    out += bytes([cu_idx]) + compact_u16(0) + compact_u16(5) + bytes([2]) + struct.pack("<I", CU_LIMIT)
    out += bytes([cu_idx]) + compact_u16(0) + compact_u16(9) + bytes([3])
    if len(out) != OFF_CU_PRICE:
        raise SystemExit(f"cu price offset {len(out)} != {OFF_CU_PRICE}")
    out += bytes(8)
    out += bytes([exec_idx]) + compact_u16(35)
    if len(out) != 1244:
        raise SystemExit(f"accs offset {len(out)}")
    out += bytes(mapping)
    out += compact_u16(25)
    if len(out) != 1280:
        raise SystemExit(f"data offset {len(out)}")
    out += ixdata
    if len(out) != TX_LEN:
        raise SystemExit(f"tx len {len(out)} != {TX_LEN}")
    return bytes(out)


def patch(tmpl: bytes, direction: int, amount_in: int, min_profit: int,
          blockhash: bytes, cu_price: int) -> bytes:
    out = bytearray(tmpl)
    out[OFF_BLOCKHASH:OFF_BLOCKHASH + 32] = blockhash
    out[OFF_CU_PRICE:OFF_CU_PRICE + 8] = struct.pack("<Q", cu_price)
    out[OFF_DIRECTION] = direction
    out[OFF_AMOUNT_IN:OFF_AMOUNT_IN + 8] = struct.pack("<Q", amount_in)
    out[OFF_MIN_PROFIT:OFF_MIN_PROFIT + 8] = struct.pack("<Q", min_profit)
    return bytes(out)


def sign_tx(payer: Keypair, tx: bytes) -> bytes:
    sig = bytes(payer.sign_message(tx[OFF_MSG:OFF_MSG + MSG_LEN]))
    if len(sig) != 64:
        raise SystemExit("bad sig")
    out = bytearray(tx)
    out[OFF_SIG:OFF_SIG + 64] = sig
    return bytes(out)


def inspect_keys(keys: list[str], our_exec: str) -> list[dict]:
    accs = d.get_multiple(keys + [our_exec, CU_PROG])
    rows = []
    for i, k in enumerate(keys):
        a = accs[i]
        rows.append({
            "i": i,
            "name": NAMES[i],
            "pubkey": k,
            "signer": bool(ACC_SIGNER[i]),
            "writable": bool(ACC_WRITE[i]),
            "exists": bool(a),
            "owner": (a or {}).get("owner"),
            "dlen": len(a["data"]) if a else 0,
            "executable": bool((a or {}).get("executable")),
        })
    rows.append({
        "i": "exec",
        "name": "OUR_EXEC",
        "pubkey": our_exec,
        "signer": False,
        "writable": False,
        "exists": bool(accs[35]),
        "owner": (accs[35] or {}).get("owner"),
        "dlen": len(accs[35]["data"]) if accs[35] else 0,
        "executable": bool((accs[35] or {}).get("executable")),
    })
    return rows


def simulate(tx: bytes) -> dict:
    import base64

    raw = base64.b64encode(tx).decode()
    print(f"  raw={len(tx)}  b64={len(raw)}  wire_max=1232")
    try:
        res = d.rpc(
            "simulateTransaction",
            [
                raw,
                {
                    "encoding": "base64",
                    "replaceRecentBlockhash": True,
                    "sigVerify": False,
                    "innerInstructions": True,
                },
            ],
        )
    except RuntimeError as e:
        msg = str(e)
        print(f"  simulate  rejected  {msg[:200]}")
        return {"err": "too_large" if "too large" in msg else "rpc", "rpc": msg, "cu": None, "logs": [], "inner": 0}
    val = res.get("value") or res
    logs = val.get("logs") or []
    err = val.get("err")
    cu = val.get("unitsConsumed")
    print(f"  simulate  err={err}  cu={cu}  logs={len(logs)}")
    for line in logs[:12]:
        print("   ", line[:180])
    if logs and len(logs) > 12:
        print("    …")
        print("   ", logs[-1][:180])
    return {"err": err, "cu": cu, "logs": logs[:24], "inner": len(val.get("innerInstructions") or [])}


def main() -> int:
    live.load_dotenv()
    payer = payer_kp()
    wallet = str(payer.pubkey())
    print(f"EXEC-LIVE-002  wallet={wallet}")

    keys = resolve(wallet)
    bad = collisions(keys)
    if bad:
        print("extra aliases (frozen compile needs only the two mint aliases):")
        for b in bad:
            print(" ", b)
        raise SystemExit("vector is not 33-unique")

    our_exec = program_v3()
    print(f"  OUR_EXEC={our_exec}  (not deployed — expected first sim error)")
    rows = inspect_keys(keys, our_exec)
    missing = [r for r in rows if r["i"] != "exec" and not r["exists"]]
    print(f"  route keys exist={35 - len(missing)}/35  missing={len(missing)}")
    for r in missing:
        print(f"    missing [{r['i']:02}] {r['name']} {r['pubkey'][:8]}..")

    tmpl = compile_template(keys, our_exec)
    print(f"  compile ok  len={len(tmpl)}  nkeys={tmpl[OFF_NKEYS]}")

    DEPLOY.mkdir(parents=True, exist_ok=True)
    (DEPLOY / "keys.bin").write_bytes(b"".join(d.b58decode(k) for k in keys))
    (DEPLOY / "exec.bin").write_bytes(d.b58decode(our_exec))
    (DEPLOY / "template.bin").write_bytes(tmpl)

    bh = d.rpc("getLatestBlockhash", [{"commitment": "confirmed"}])
    blockhash = d.b58decode(bh["value"]["blockhash"])
    tx = patch(tmpl, 0, TINY_IN, MIN_PROFIT, blockhash, 1)
    signed = sign_tx(payer, tx)
    if signed[0] != 1 or signed[65] != 1:
        raise SystemExit("legacy header")
    print("  signed  1305-byte frozen template")

    sim = simulate(signed)

    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "wallet": wallet,
        "our_exec": our_exec,
        "our_exec_on_chain": bool(d.get_multiple([our_exec])[0]),
        "pair_dlmm": PAIR_DLMM,
        "pair_pump": PAIR_PUMP,
        "tx_len": len(signed),
        "nkeys": 35,
        "writable_unique": 15,
        "missing": [{"i": r["i"], "name": r["name"], "pubkey": r["pubkey"]} for r in missing],
        "accounts": rows,
        "simulate": sim,
        "note": "OUR_EXEC is the v3 key for tomorrow's deploy. Simulate is expected to stop there until it is executable. Template metas are the live vector.",
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (OUT / "keys.json").write_text(
        json.dumps([{"i": i, "name": NAMES[i], "pubkey": keys[i]} for i in range(35)], indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "signed.tx").write_bytes(signed)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
