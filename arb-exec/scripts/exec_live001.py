#!/usr/bin/env python3
"""EXEC-LIVE-001 — immutable BPF-2 deploy + live CPI simulate. Never prints secrets.
Never sendTransaction of the arb. Deploy / ATA / wrap only.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arb-cap"))
import live001 as live  # noqa: E402
import record_dlmm as d  # noqa: E402

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.message import Message
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / ".deploy"
SO_PATH = ROOT / "program" / "route0.so"
REPORT_DIR = ROOT.parent / "arb-cap" / "exec_live001"

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

DISC = b"ARBEXEC0"
TINY_IN = 10_000
MIN_PROFIT_GUARD = 1_000_000_000
CU_LIMIT = 400_000


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


def blockhash() -> Hash:
    bh = d.rpc("getLatestBlockhash", [{"commitment": "confirmed"}])
    return Hash.from_string(bh["value"]["blockhash"])


def rpc_once(method: str, params):
    import urllib.request

    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        d.rpc_url(), data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        obj = json.loads(r.read().decode())
    if "error" in obj:
        raise RuntimeError(obj["error"])
    return obj["result"]


def send_tx(tx: Transaction) -> str:
    raw = base64.b64encode(bytes(tx)).decode()
    return rpc_once(
        "sendTransaction",
        [raw, {"encoding": "base64", "skipPreflight": True, "preflightCommitment": "processed"}],
    )


def confirm(sig: str, timeout: float = 90.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = rpc_once("getSignatureStatuses", [[sig], {"searchTransactionHistory": True}])
        val = (st.get("value") or [None])[0]
        if val:
            if val.get("err"):
                raise RuntimeError(f"tx err {val['err']}")
            if val.get("confirmationStatus") in ("confirmed", "finalized"):
                return
        time.sleep(0.4)
    raise TimeoutError("confirm timeout")


def send_ok(payer: Keypair, ixs: list[Instruction], extra: list[Keypair] | None = None) -> str:
    signers = [payer] + (extra or [])
    last = None
    for _ in range(6):
        try:
            msg = Message.new_with_blockhash(ixs, payer.pubkey(), blockhash())
            tx = Transaction.new_unsigned(msg)
            tx.sign(signers, msg.recent_blockhash)
            sig = send_tx(tx)
            confirm(sig)
            return sig
        except Exception as e:
            last = e
            if "Blockhash" not in str(e) and "blockhash" not in str(e):
                raise
            time.sleep(0.3)
    raise last


def load_or_make_program_kp() -> Keypair:
    DEPLOY.mkdir(parents=True, exist_ok=True)
    path = DEPLOY / "program.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Keypair.from_bytes(bytes(raw))
    kp = Keypair()
    path.write_text(json.dumps(list(bytes(kp))) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return kp


def resolve(wallet: str) -> dict:
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
    event_dlmm = d._pk(d.find_pda([b"__event_authority"], d.b58decode(DLMM)))
    pacc = d.get_multiple([PAIR_PUMP])[0]
    p = live.parse_pump_pool(pacc["data"]) if pacc else None
    if not p:
        raise SystemExit("pump parse failed")
    gcfg = d._pk(d.find_pda([b"global_config"], d.b58decode(PUMP)))
    ev_pump = d._pk(d.find_pda([b"__event_authority"], d.b58decode(PUMP)))
    gvol = d._pk(d.find_pda([b"global_volume_accumulator"], d.b58decode(PUMP)))
    uvol = d._pk(d.find_pda([b"user_volume_accumulator", d.b58decode(wallet)], d.b58decode(PUMP)))
    fee_cfg = d._pk(d.find_pda([b"fee_config", d.b58decode(gcfg)], d.b58decode(FEE_PROG)))
    creator_ata = "75mhQAcZeGKiL3wcuuVjTjg2SHJewZuQpd59ukiG24yv"
    creator_auth = "F2Ne1XNs5f7LQNBdfB5WE69AGunwjAa6akdVGfVXiZxY"
    proto = "G5UZAVbAf46s7cKWoyKu8kYTip9DGTpbLZ2qa9Aq69dP"
    proto_ata = ata(proto, SOL, TOKENKEG)
    user_quote = ata(wallet, SOL, TOKENKEG)
    user_base = ata(wallet, mint_x, TOKEN2022)
    frozen = [
        wallet, user_quote, user_base, TOKENKEG, SYSTEM, ATA_PROG, MEMO, DLMM,
        event_dlmm, PAIR_DLMM, DLMM, d._pk(lb["vault_x"]), d._pk(lb["vault_y"]),
        oracle, DLMM, mint_x, mint_y, bins[0], bins[1], PUMP, ev_pump, PAIR_PUMP,
        gcfg, fee_cfg, FEE_PROG, mint_x, mint_y, d._pk(p["vault_base"]),
        d._pk(p["vault_quote"]), proto, proto_ata, creator_ata, creator_auth,
        gvol, uvol,
    ]
    pump_ix = [
        PAIR_PUMP, wallet, gcfg, mint_x, mint_y, user_base, user_quote,
        d._pk(p["vault_base"]), d._pk(p["vault_quote"]), proto, proto_ata,
        TOKEN2022, TOKENKEG, SYSTEM, ATA_PROG, ev_pump, PUMP, creator_ata,
        creator_auth, gvol, FEE_PROG, fee_cfg,
    ]
    return {
        "frozen": frozen,
        "pump_ix": pump_ix,
        "user_quote": user_quote,
        "user_base": user_base,
        "mint_x": mint_x,
        "bins": bins,
        "active_id": lb["active_id"],
        "oracle": oracle,
        "uvol": uvol,
    }


def deploy_or_require(program: Keypair, so: bytes) -> dict:
    """Loader-v3 only. SIMD-0093 disabled BPF2 writes; do not create BPF2 accounts."""
    pid = str(program.pubkey())
    existing = d.get_multiple([pid])[0]
    if existing and existing.get("executable"):
        print(f"  already deployed {pid} dlen={len(existing['data'])}")
        return {"program_id": pid, "already": True, "bytes": len(existing["data"])}
    rent = d.rpc("getMinimumBalanceForRentExemption", [len(so)])
    print(f"  not executable  {pid}  so={len(so)}  rent={rent/1e9:.6f}  need_peak~{2*rent/1e9:.3f} SOL")
    raise SystemExit(
        "OUR_EXEC is not on-chain. Deploy with loader-v3 only "
        "(`solana program deploy --use-rpc`). Do not use BPFLoader2."
    )


def ensure_ata(payer: Keypair, owner: str, mint: str, token_program: str) -> str:
    pk = ata(owner, mint, token_program)
    if d.get_multiple([pk])[0]:
        return pk
    ix = Instruction(
        Pubkey.from_string(ATA_PROG),
        bytes([1]),  # CreateIdempotent
        [
            AccountMeta(payer.pubkey(), True, True),
            AccountMeta(Pubkey.from_string(pk), False, True),
            AccountMeta(Pubkey.from_string(owner), False, False),
            AccountMeta(Pubkey.from_string(mint), False, False),
            AccountMeta(Pubkey.from_string(SYSTEM), False, False),
            AccountMeta(Pubkey.from_string(token_program), False, False),
        ],
    )
    sig = send_ok(payer, [ix])
    print(f"  ata {pk[:8]}.. {sig[:12]}..")
    return pk


def wrap_wsol(payer: Keypair, wsol_ata: str, lamports: int) -> None:
    info = d.get_multiple([wsol_ata])[0]
    have = d.token_amount(info["data"]) if info else 0
    if have >= lamports:
        print(f"  wsol already {have}")
        return
    need = lamports - have
    ix_tr = transfer(
        TransferParams(from_pubkey=payer.pubkey(), to_pubkey=Pubkey.from_string(wsol_ata), lamports=need)
    )
    # syncNative = instruction 17
    ix_sync = Instruction(
        Pubkey.from_string(TOKENKEG),
        bytes([17]),
        [AccountMeta(Pubkey.from_string(wsol_ata), False, True)],
    )
    sig = send_ok(payer, [ix_tr, ix_sync])
    print(f"  wrap {need} {sig[:12]}..")


def pack_ix(direction: int, amount_in: int, min_profit: int) -> bytes:
    return DISC + bytes([direction]) + struct.pack("<QQ", amount_in, min_profit)


def simulate(payer: Keypair, program: str, accs: list[str], data: bytes, writable: set[str]) -> dict:
    metas = []
    for a in accs:
        metas.append(
            AccountMeta(
                Pubkey.from_string(a),
                a == str(payer.pubkey()),
                a in writable or a == str(payer.pubkey()),
            )
        )
    ixs = [
        set_compute_unit_limit(CU_LIMIT),
        set_compute_unit_price(1),
        Instruction(Pubkey.from_string(program), data, metas),
    ]
    msg = Message.new_with_blockhash(ixs, payer.pubkey(), blockhash())
    tx = Transaction.new_unsigned(msg)
    tx.sign([payer], msg.recent_blockhash)
    raw = base64.b64encode(bytes(tx)).decode()
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
    val = res.get("value") or res
    err = val.get("err")
    cu = val.get("unitsConsumed")
    logs = val.get("logs") or []
    inner = val.get("innerInstructions") or []
    cpi = []
    for g in inner:
        for ix in g.get("instructions") or []:
            cpi.append(ix.get("programId") or "")
    print(f"  err={err} cu={cu} inner={len(inner)} cpi={cpi[:6]}")
    for line in logs[-8:]:
        print("   ", line[:180])
    return {"err": err, "cu": cu, "inner": len(inner), "cpi": cpi, "logs": logs[-16:]}


def main() -> int:
    live.load_dotenv()
    payer = payer_kp()
    wallet = str(payer.pubkey())
    bal = d.rpc("getBalance", [wallet])
    lamports = bal["value"] if isinstance(bal, dict) else bal
    print(f"EXEC-LIVE-001  wallet={wallet}  sol={lamports/1e9:.6f}")

    if not SO_PATH.exists():
        raise SystemExit(f"missing {SO_PATH}")
    so = SO_PATH.read_bytes()
    print(f"  so={len(so)} bytes")

    acc = resolve(wallet)
    print(f"  active={acc['active_id']} quote={acc['user_quote'][:8]} base={acc['user_base'][:8]}")

    program = load_or_make_program_kp()
    print(f"  OUR_EXEC={program.pubkey()}")
    dep = deploy_or_require(program, so)
    pid = dep["program_id"]

    ensure_ata(payer, wallet, SOL, TOKENKEG)
    ensure_ata(payer, wallet, acc["mint_x"], TOKEN2022)
    wrap_wsol(payer, acc["user_quote"], TINY_IN)

    writable = {
        wallet, acc["user_quote"], acc["user_base"],
        PAIR_DLMM, acc["frozen"][11], acc["frozen"][12], acc["oracle"],
        acc["bins"][0], acc["bins"][1], PAIR_PUMP, acc["frozen"][27],
        acc["frozen"][28], acc["frozen"][30], acc["frozen"][31], acc["uvol"],
    }
    accs = acc["frozen"] + [TOKEN2022] + acc["pump_ix"]

    print("sim live tiny dir0 min_profit=1")
    r0 = simulate(payer, pid, accs, pack_ix(0, TINY_IN, 1), writable)
    print("sim guard dir0 min_profit=1SOL")
    r1 = simulate(payer, pid, accs, pack_ix(0, TINY_IN, MIN_PROFIT_GUARD), writable)
    print("sim guard dir1 min_profit=1SOL")
    r2 = simulate(payer, pid, accs, pack_ix(1, TINY_IN, MIN_PROFIT_GUARD), writable)

    bal2 = d.rpc("getBalance", [wallet])
    left = bal2["value"] if isinstance(bal2, dict) else bal2
    report = {
        "wallet": wallet,
        "sol_before": lamports / 1e9,
        "sol_after": left / 1e9,
        "program_id": pid,
        "program_bytes": len(so),
        "deploy": {k: v for k, v in dep.items() if k != "rent"} | {"rent_sol": dep.get("rent", 0) / 1e9 if dep.get("rent") else None},
        "pair_dlmm": PAIR_DLMM,
        "pair_pump": PAIR_PUMP,
        "tiny_in": TINY_IN,
        "sim_live_min1": r0,
        "sim_guard_dir0": r1,
        "sim_guard_dir1": r2,
        "note": "51k shim CU discarded; unitsConsumed is live",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (REPORT_DIR / "resolve.json").write_text(
        json.dumps({"frozen": acc["frozen"], "pump_ix": acc["pump_ix"], "program_id": pid}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {REPORT_DIR}  leftover_sol={left/1e9:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
