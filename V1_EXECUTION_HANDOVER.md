# V1 Execution Handover

**Audience:** second developer and their coding agents.  
**Goal:** shortest credible path from a detected positive arbitrage to an executable, then (only with explicit human approval) a funded send that can produce real net PnL.  
**Aspirational early target:** ~$50/hour once sufficiently stable. **This target is not proven.** No artifact in this repo demonstrates sustained profitable funded arb.

This document is traced from implementation and cap tickets. If something is not in the tree, it is marked **unknown / unverified**.

**Do not invent names.** The repo does **not** contain `native_ready`, `policy_admitted`, or `ARB_SEND`. Closest production names are listed in §7.

---

## 0. How to read this repo

There is **no root README**. Six trees, Linux-only CMake (Windows checkout is source + Python; C binaries are built on the Frankfurt box).

| Tree | Role |
|------|------|
| `arb-core/` | Frozen quote/apply kernels, universe, frame, trigger, paper eval, `opportunity_t` |
| `arb-feed/` | UDP capture + `paper_orbit` (production-shaped **paper** searcher) |
| `arb-exec/` | Templates, sign, SWQOS, on-chain programs, oneshot / hops control plane |
| `arb-state/` | Yellowstone AUTH writer (`state008.py`) + shadow/soak |
| `arb-cap/` | Experiment tickets, reducers, historical metrics |
| `arb-nic/` | Frozen RX/XDP bench. **Not** the V1 bot. No FPGA in this tree. |

Deployment paths in scripts assume `/home/louis/...` on Frankfurt (`TOMORROW.md` SSH `louis@195.242.152.178`). This workspace does not prove that box is currently running any process.

---

## 1. Current system and runtime dataflow

### 1.1 What the system is

A **paper searcher** follows OrbitFlare shred captures, frames trigger `N`, installs **predecessor AUTH** from shared memory written by a **separate** Yellowstone process, optionally applies a **transaction-local overlay** (`tx_exact`), quotes DLMM↔Pump cycles, and journals opportunities. **Default production does not send arb.**

Live send, when armed, is a **separate oneshot process** that tails `opp_synced.jsonl`, patches a **resident v0+ALT template**, signs, and writes bytes to `exec_swqos_racer` over a UNIX socket.

```
OrbitFlare UDP
    → arb-feed feed_live  (FEEDCAP1 .cap)     [ingest; do not redesign for V1]
    → paper_orbit follow  (no bind, no .cap write, no send by default)

Shyft Yellowstone gRPC
    → arb-state/shyft/state008.py
    → AUTH mmap (/dev/shm/arb_auth009) + recon.bin
    → paper_orbit install_auth / recon_drain

paper_orbit
    → shred_parse → classify_n | trigger_scan_at
    → close_candidate → frame_concat / frame_around_sig → trigger_admit_at
    → install_auth (trigger + route0 partner)
    → txo_scan / txo_apply  (TX_EXACT if overlay succeeds)
    → state_observe → hot_decide  → opportunity_t
    → note_searchable → gate JSON (would_send_new)
    → if mut_authoritative + opp.valid → opp_synced.jsonl
    → [compile FUNDED=1 only] route0_v0_patch + route0_v0_sign  (dummy 0xBB blockhash; NO swqos_send)

oneshot_live.py  [env FUNDED=1 + ARMED + plane templates]
    → tail opp_synced.jsonl
    → framed_ready + size_gate
    → exec_live002b.patch + sign_v0
    → UNIX socket → exec_swqos_racer → swqos_send
    → poll_sig + classify_race → RESULT.json + DISARMED
```

### 1.2 Two processes, not one executable

| Process | Binary / script | Sends arb? |
|---------|-----------------|------------|
| Capture | `arb-feed/build/feed_live` | No (`PAPER=1` in `orbitflare_paper.sh`) |
| Search | `arb-feed/build/paper_orbit` | No unless compile-time `FUNDED=1` (still no network send) |
| AUTH | `python3 arb-state/shyft/state008.py` | No (`FUNDED=0` in start scripts) |
| Control plane | `arb-exec/scripts/hops_live.py`, `alt_plane.py` | No |
| Live oneshot | `arb-exec/scripts/oneshot_live.py` | **Yes** only if `FUNDED=1` |
| Racer | `arb-exec/build/exec_swqos_racer` | Transport only |

**Unknown:** whether a future single-process live searcher exists. The tree is two-process (shred paper + geyser AUTH).

### 1.3 What “positive opportunity” means

1. **Framed / policy path:** `state_observe` → `hot_decide` (`arb-core/src/hot.c`). Counted as `acc.opp` when `dec.opp.valid`.
2. **Searchable journal path:** `paper_eval_trigger` (`arb-core/src/paper.c`) when `pop.opp.valid`. Gross positive is `gross > 0` (`gross_pos` in gate JSON).
3. **Handoff struct** (`arb-core/include/opportunity.h`):

```c
typedef struct {
    uint32_t route_id;
    uint64_t amount_in, amount_out, gross_profit;
    uint8_t  direction, valid;
} opportunity_t;
```

Gross is **protocol profit only**. Tips / CU / SWQOS are exec’s problem (`opportunity.h` comment).

There is **no in-memory exec queue**. `paper_orbit` journals; oneshot tails a file.

---

## 2. Repository map

### 2.1 Prediction / search (first developer — do not rewrite for “execution quality”)

| Module | Paths | Notes |
|--------|-------|--------|
| DLMM apply/quote/cache | `arb-core/src/dex/meteora_dlmm.c`, `dlmm_cache.c`, `include/dlmm_*.h` | CORE-003–005 **frozen** |
| Pump apply/quote | `arb-core/src/dex/pump.c`, `include/pump.h` | CORE-006 **frozen**; PUMP-AUTH-016 does **not** change blob layout |
| Cycle / size | `arb-core/src/cycle.c`, `hot.c` | CORE-007/008 **frozen** |
| Paper quote/eval | `arb-core/src/paper.c`, `include/paper.h` | `PAPER_SIGNED` / `PAPER_EXEC_FAMILY_MISSING` / `PAPER_STATE_INSUFFICIENT` |
| State policy | `arb-core/src/state003.c`, `include/state003.h` | `state_observe` never writes canonical S |
| State apply harness | `arb-core/src/state_apply.c` | Used by shyft `apply_n.py` |
| Trigger / swapix / frame | `arb-core/src/trigger.c`, `swapix.c`, `frame.c`, `classify_n.c`, `tx_n.c` | TRIGGER-011 research still open |
| ALT cache (search) | `arb-core/src/alt_cache.c` | Miss → no invented addresses |
| Universe | `arb-core/src/universe*.c`, `live.c` | `liveuniv.bin` |
| TX overlay (S′) | `arb-feed/src/tx_overlay.c`, `include/tx_overlay.h` | Sets `tx_exact`; soaking |
| AUTH consumer | `arb-feed/src/authpub.c` | `authpub_pred` |
| AUTH producer | `arb-state/shyft/state008.py`, `authpub.py`, `txbarrier.py`, `bank_context.py` | |
| Shadow / soak | `arb-state/shyft/shadow.py`, `start_*.sh` | |
| Pump 012–016 research | `arb-cap/pump012/*`, `arb-state/shyft/overlay_n.py` | Overlay Python; “No C kernel change” in overlay_n |
| Paper orchestrator (search half) | `arb-feed/src/paper_orbit.c` | Framing, AUTH, overlay, decide, gate |

### 2.2 Execution (second developer primary)

| Module | Paths | Notes |
|--------|-------|--------|
| Route0 accounts (legacy) | `arb-exec/src/route0.c`, `include/route0.h` | EXEC-001 **frozen** |
| Legacy template | `arb-exec/src/tx_template.c` | EXEC-002 **frozen** |
| v0 + ALT template | `arb-exec/src/route0_v0.c`, `include/route0_v0.h` | EXEC-LIVE-002B; `V0_TX_LEN` 623 |
| Sign | `arb-exec/src/sign.c` | EXEC-003 **frozen** offsets |
| Nonce ring | `arb-exec/src/nonce.c`, `ctrl.c` | EXEC-004 **frozen**; oneshot currently uses **recent blockhash**, not this ring |
| Families 1–4 | `arb-exec/src/route_fam.c` | Non-route0 pack hooks |
| SWQOS | `arb-exec/swqos/src/lib.rs`, `include/swqos.h` | `swqos_send` |
| Racer | `arb-exec/tests/exec_swqos_racer.c` | UNIX server for oneshot |
| Oneshot | `arb-exec/scripts/oneshot_live.py` | Only funded arb path in tree |
| Patch/sign Python | `arb-exec/scripts/exec_live002b.py` | `patch`, `sign_v0`, `lookup_prepared`, `AltPlaneMiss` |
| ALT / hops plane | `arb-exec/scripts/alt_plane.py`, `hops_live.py`, `hops_plane.py`, `hops_vector.py`, `hops_message.py` | `FUNDED` stays 0 in hops_live header |
| On-chain | `arb-exec/program/` (OUR_EXEC), `arb-exec/program_hops/` (ARBHOPS0) | `program_dlmm2/` **superseded** — do not deploy |

### 2.3 Shared infrastructure

| Area | Paths |
|------|--------|
| Opportunity contract | `arb-core/include/opportunity.h` (exec has a copy under `arb-exec/include/opportunity.h`) |
| Sync journal | `arb-core/src/syncrec.c` — `syncrec_decision`, `syncrec_exec` |
| Hurdles | `arb-core/include/hops_hurdle.h` — `hops_hurdle_for_seq` |
| Ingest | `arb-feed/src/live.c`, `udp_source.c`, `recorder.c`, `include/rx.h` |
| Capture ops | `arb-feed/scripts/orbitflare.env`, `orbitflare_paper.sh`, `process_health.*` |

### 2.4 Telemetry / paper / soak

| Area | Paths |
|------|--------|
| Gate + opp journals | `paper_orbit` `--audit` → default `~/captures/paper_orbit/opp_synced.jsonl` |
| Sync bin | `--sync` → `syncrec` |
| Stats | `--stats` |
| Funnel aggregators | `arb-cap/state007/agg_funnel007.py`, `arb-cap/oneshot/audit_funnel_window.py`, `audit_nosend.py`, `arb-cap/regress/scan_hour.py` |
| Shadow scoreboard | `arb-cap/state008/SCOREBOARD.md` |
| Paper tickets | `arb-cap/paper002` … `paper004`, `paper_live001` |
| Exec tickets | `arb-cap/exec_live001`, `exec_live002`, `exec_live002b`, `exec_ctrl` |
| SWQOS bench | `arb-cap/swqos_bench/` |

### 2.5 Transaction construction / signing / submission

| Step | Implementation |
|------|----------------|
| C compile/patch | `route0_v0_compile`, `route0_v0_patch`, `route0_v0_sign` |
| Python patch/sign | `exec_live002b.patch`, `exec_live002b.sign_v0` |
| Submit | `swqos_send` / racer socket `/home/louis/arb-cap/oneshot/swqos.sock` |
| Stub (not prod) | `leader_send` (`arb-exec/src/leader.c`) — local UDP only |
| NIC txgen | `arb-nic/src/txgen.c` — UDP load gen, **not** Solana submit |

### 2.6 Route layouts

| Layout | Path |
|--------|------|
| 35-account EXEC-001 | `route0.h` / `route0.c` |
| v0 ALT wr/ro | `route0_v0.h` (wr[14]+ro[9]+fee accounts) |
| SIMD-0385 frame | `arb-core/src/frame.c` (`frame_v1_layout`) |
| Hops compiler | `hops_message.py` `compile_message` |
| Universe routes | `liveuniv` / `routes_by_pool` (CORE-009) |

### 2.7 Configuration

| Kind | Where |
|------|--------|
| Feed | `arb-feed/scripts/orbitflare.env` — `CAPTURE_DIR`, `UDP_PORT`, `PAPER=1` |
| Paper orbit | `PAPER_UNIV`, `PAPER_SYNC`, `PAPER_PEND`, `PAPER_RECON`, `PAPER_AUDIT`, `PAPER_STATS`, `PAPER_SECONDS` |
| AUTH | `STATE008_CAP`, `STATE_APPLY`, `SHYFT_GRPC_URL`, `SHYFT_TOKEN` / `SHYFT_X_TOKEN` (`arb-state/shyft/config.py`) |
| Send | **`FUNDED`** env in `oneshot_live.py` (default `"0"`); **compile macro** `FUNDED` in `paper_orbit.c` (default `0`) |
| SWQOS / wallet | `SWQOS_KEY` / `SWQOS_API_KEY`, `PRIVATE_KEY`, `PUBLIC_KEY`, `RPC_URL` / `HELIUS_RPC_URL` — also root `.env` (secrets; never commit) |
| Oneshot constants | `MAX_IN=50_000_000`, `HURDLE=525000`, `CU_LIMIT=400_000`, `CU_PRICE=800_000` in `oneshot_live.py` |
| Hardcoded Frankfurt files | `AUDIT`, `UNIV`, `PLANE`, `S007_READY`, `SWQOS_SOCK` in `oneshot_live.py` |

---

## 3. Ownership boundary

### 3.1 First developer (you) — remains

Pump state prediction, **PUMP-AUTH-016**, transaction-local reconstruction (`tx_overlay` / overlay_n), AUTH generations, shadow mismatches, protocol semantics, quote correctness (`quote == apply`), route **detection** (which pools/hops exist and whether S′ is exact), TRIGGER-011 exact-N research.

**Do not hand these to execution as “fix the send rate.”** A wrong S′ that becomes a send is a loss.

### 3.2 Second developer — owns

The path **after** a journaled positive / synced opportunity: layout coverage, ALT templates, account completeness for **OUR_EXEC / ARBHOPS0**, size ≤ 1232, policy-to-send gates that are **exec-side**, signing, SWQOS, landing telemetry, oneshot/racer/plane, converting `would_send_new` into **executable templates** and (later) `sent`.

### 3.3 Shared / negotiate, do not freelance

| Surface | Why |
|---------|-----|
| `paper_orbit.c` audit fields / `opp_synced` schema | Oneshot consumes it |
| `would_send_new` definition | Search writes it; exec must not silently change meaning |
| `race_ready` in JSON vs plane `RACE_READY` | **Two different predicates** (§4, §13) |
| `FUNDED` | Human-only |
| Frozen kernels / EXEC-001–004 offsets | Breaks both sides |

### 3.4 Out of scope for V1 (both)

FPGA/NIC (`arb-nic` frozen; physical X710 zero-copy **stopped**), new feeds (DoubleZero, Rabbit, Flowra are observe/research), market making, massive venue expansion, theoretical networking redesign. **Ingest is good enough for V1** unless it **directly** blocks constructing or sending a tx (e.g. you cannot frame at all). Do not treat OrbitFlare ~7k shred/s vs a prior ~50k trial as a redesign brief (`paper_orbit.c` comment: log, do not assume equivalence).

Repo READMEs do not name “developer 1 / 2.” The split above is the working contract for this handover.

---

## 4. Positive-arb-to-send funnel (every gate found)

Read **top to bottom**. Most positives die early. Names in backticks are actual fields or functions.

### 4.1 Ingest / frame / admit (`close_candidate`)

| Bucket | Code | Effect |
|--------|------|--------|
| Bad shred | `paper_orbit` loop | `acc.bad` |
| Frame incomplete | `FRAME_INCOMPLETE` | Hold / retry; `acc.frame_incomplete` |
| Frame invalid | `FRAME_INVALID` | `acc.frame_invalid` |
| Raw admission fail | `trigger_admit_at` ≠ `TRIG_EXACT` | JSON `raw_admission` `accepted:0` |
| ALT miss / uncertain | `TRIG_ALT_MISS`, `TRIG_ALT_UNCERTAIN` | `acc.trig_alt_miss`; no invented keys |
| Relevant unknown | `TRIG_RELEVANT_UNKNOWN` | Journal `kind=trigger011`; **no** `close_candidate` / no S′ |
| Duplicate | `hot_seen_first` | `acc.dup` |

### 4.2 Pool / AUTH / overlay / observe (`consider_framed`)

| Bucket | Code | Effect |
|--------|------|--------|
| Unknown pool | `pool_table_get` fail | `unknown_pool`; gate with `known=0` |
| AUTH miss (trigger or partner) | `install_auth` ≠ 0 | `auth_pub_miss`, `missing_state`, `state_mark_stale` |
| Overlay not TX_EXACT | `txo_scan`/`txo_apply` fail or ix-only | `ix_exact++` (paper-observable, **not fundable**) |
| Overlay TX_EXACT | apply ok | `tx_exact++` |
| Missing bin / apply / unhealthy | `state_observe` → `ST3_MISSING_BIN`, `ST3_APPLY_FAIL`, `ST3_UNHEALTHY` | `missing_state`; often return before opp |
| No opportunity | `!dec.opp.valid` / `ST3_NO_OPP` | No `opp_synced` |
| Stale version | `hot_stale` | `acc.stale` (does **not** alone block audit) |
| Freshness drop | `!mut_auth` | `fresh_drop` JSON; **blocks** `opp_synced` |
| Partner not sendable | partner `g_s007_updating` or `!state_sendable` | `mut_auth=0` |

`mut_auth` for `opp_synced` (`consider_framed`): `state_sendable` + `auth_ns` + `g_s007_ready` + trigger pool not updating + route0 partner sendable.

### 4.3 Searchable / “would send” (`note_searchable` → `write_gate`)

Requires `paper_eval_trigger` success and `pop.opp.valid`.

| Field | Meaning |
|-------|---------|
| `searchable` | Eval succeeded |
| `gross_pos` | `gross_profit > 0` |
| `cap_ok` | `paper_quote_route(..., 50_000_000)` and `cap_out > 50M` |
| `cap_gross` | `cap_out - 50M` |
| `cap_hurdle` | `cap_gross > hops_hurdle_for_seq(seq)` |
| `synced_all` / `age32_all` / `mut_ok_all` | Per-hop scans (`age32` is **journaled only**) |
| `mut_authoritative` | Every hop: `g_s007_ready` ∧ not updating ∧ `state_sendable` ∧ `auth_ns` |
| `exec_fam` | Family 0, 5, or 6 |
| **`would_send_new`** | **`cap_hurdle && mut_authoritative` only** |

**`would_send_new` does not check** `FUNDED`, SWQOS, plane templates, `tx_exact`, `exec_fam`, or oneshot `HURDLE`. A 3-hop `family=255` can still be `would_send_new` (STATE-007 example).

Paper reasons (`paper.h`): `0` signed-ready family, `1` exec family missing, `2` state insufficient.

### 4.4 Execution readiness (plane / oneshot)

| Bucket | Where | Meaning |
|--------|-------|---------|
| Missing layout / templates | `load_race_plane` | Need `RACE_READY` **and** `tmpl0` **and** `tmpl1` |
| `vector_ready` | `hops_live.py` `publish` | `ata_ready && size_ok` |
| `size_ok` | hops_live | Offline size row `ok` and raw ≤ `V0_MAX` |
| Plane `RACE_READY` / `race_ready` | hops_live ~994–996 | **Prior** Custom(6) proof **and** `vector_ready`. **Publish never invents it.** |
| Audit `race_ready` | `paper_orbit` | **`ov.tx_exact` only** — **not** the plane flag |
| `framed_ready` | `oneshot_live.py` | `frame.class=="framed"` ∧ audit `race_ready==1` ∧ file `S007_READY` ∧ pool in resident `_plane` |
| `size_gate` | oneshot | `framed_ready` + direction 0/1 + not `route_blocked` + `send_quote.cap_ok` + `MAX_IN` in range + `cap_gross > HURDLE` (525000) |
| Tx size | `racer_send` | `len(tx)` not in `[64, 1232]` |
| `AltPlaneMiss` | `fire` | No resident template / missing dir template |
| Blockhash | `resident_bh` | Must be 32 bytes (RPC loop) |
| Wallet | `main` | Native + WSOL wrap `MAX_IN`; refuse if too small |
| `SEND_BLOCKED` | `COOLDOWN.json` | After 3 `TRIGGER_MISSING` on a pool |
| Oneshot `FUNDED` | env | Else print `SEND=0` and exit 0 |
| Already armed | `ARMED` exists | Refuse |
| Missing racer / audit / SWQOS_KEY | `main` | Exit 1 |
| C sign (paper) | `route0_v0_patch/sign` | Only if compile `FUNDED` + `tx_exact` + `ROUTE_DLMM_PUMP`; dummy blockhash |

### 4.5 Policy / stale profit

| Bucket | Notes |
|--------|-------|
| Stale Custom(6) | Oneshot `why=stale_custom6` — InstructionError Custom 6 |
| TRIGGER_MISSING | Custom 6 + trigger N `disappeared` |
| Frozen 50M send | Oneshot **never** uses optimal `arb.amount_in` (`size_gate` comment) |
| Hurdle mismatch | Paper uses **per-seq** `hops_hurdle_for_seq`; oneshot uses **flat 525k** |
| STATE-007 vs 008 READY | Oneshot still requires `/home/louis/captures/state007/READY` while AUTH writer is **state008** |

### 4.6 Signing / simulation / send restrictions

| Bucket | Where |
|--------|-------|
| `sign_fail` | `exec_swqos_v1.c` benches |
| Simulate-only | `exec_live002.py`, `exec_live002b.py`, `hops_sim.py` — **never send arb** |
| Custom(6) matrix | hops / fam6 gates; skipped without `HOPS_PROGRAM` / `FAM6_PROGRAM` |
| SWQOS fail | `swqos_rc != 0` → `never_lands_swqos_fail` |
| Never lands | No status after poll |
| `program_error` | Other on-chain err |
| `success` | confirmed/finalized, no err |
| Race classes | `WIN`, `LOST_RACE`, `OURS_NEVER_LANDS`, `CUSTOM6`, `CUSTOM6_NO_COMPETITOR`, `TRIGGER_MISSING` |
| Docs block send | Almost every STATE/TRIGGER/PUMP ticket: **FUNDED=0** |
| TRIGGER-011 verdict | **FAIL — FUNDED REMAINS BLOCKED** (router exact-N / predecessor) |

### 4.7 Name mapping (user terms → repo)

| Asked | Actual |
|-------|--------|
| positive | `gross_pos` / `acc.opp` / `opp_searchable` |
| prep / layout coverage | No metric named `prep`. Closest: plane `vector_ready`, `tmpl0`/`tmpl1`, `lookup_prepared` |
| native_ready | **Does not exist.** Closest: wallet native/WSOL check in oneshot `main` |
| policy_admitted | **Does not exist.** Closest: `trigger_admit_at` / `raw_admission` |
| would_send | `would_send_new` |
| sent | Oneshot fire + `swqos_rc==0`; `SYN_EXEC_SENT` **unused** |
| landed | Oneshot `why=success` / SWQOS bench `landed`; `SYN_EXEC_LAND` **unused** |

---

## 5. Exact execution path (positive → bytes → land telemetry)

### 5.1 Detection → journal (always on)

1. `consider_framed` gets `dec.opp.valid`.
2. If sendable + `mut_auth`: `acc.opp_synced++`.
3. `race_ready = ov.tx_exact`.
4. `audit_opp_synced` writes one JSON object `kind=opp_synced` including:
   - `arb.{direction,amount_in,intermediate,final,gross}`
   - `send_quote.{cap, cap_ok, cap_final, cap_gross, tiny_*}`
   - `frame.class` always `"framed"` on this writer
   - `race_ready` (= tx_exact)
   - `ix_exact`, `tx_exact`, `s_prime`, `timing.{actionable_ns,decision_ns,signed_ready_ns}`
5. Optional compile-time: `route0_v0_patch(cx->v0, &dec.opp, 1, bh, 1, tx)` with `memset(bh, 0xBB, 32)` then `route0_v0_sign` → `syncrec_exec(..., SYN_EXEC_READY)`. **No `swqos_send`.**

### 5.2 Oneshot (only funded arb send)

File: `arb-exec/scripts/oneshot_live.py`.

1. Require `FUNDED=1`, `S007_READY`, SWQOS key, racer socket, audit file, not already `ARMED`.
2. Load payer (`exec_live002b.payer_kp`), wrap WSOL, `load_race_plane()` from:
   - `/home/louis/arb-exec/.deploy/alt_plane.json`
   - `/home/louis/arb-cap/oneshot/ALT_PLANE.json`
3. Start `hash_loop` (`getLatestBlockhash` processed).
4. Write `ARMED`; `follow_new(AUDIT)` from **EOF**.
5. Keep `kind=="opp_synced"` and `framed_ready`.
6. `size_gate` → `(send=50_000_000, gross=cap_gross)` or DROP.
7. `fire`:
   - pick `tmpl0`/`tmpl1` by `direction`
   - `tx = sign_v0(payer, patch(tmpl, direction, send_lamports, MIN_PROFIT, bh, CU_PRICE, buy=...))`
   - unlink `ARMED`
   - `racer_send(tx)` length-prefixed to `swqos.sock`
   - if `rc==0`, `poll_sig(sig, 75)`
8. Classify `why`; `classify_race`; **`disarm` after exactly one attempt** (`Never retries`).

### 5.3 SWQOS / landing telemetry

| Artifact | Fields |
|----------|--------|
| stderr | `RACER_SEND rc=…`, `CLASS …` |
| `~/arb-cap/oneshot/RESULT.json` | `why`, `opp`, `fire` (`sig`, `tx_len`, `swqos_rc`, `status`, `timing.T_*`), `race` |
| `DISARMED` | same payload |
| `COOLDOWN.json` | `SEND_BLOCKED` per pool |
| SWQOS bench jsonl | `landed`, `sign_to_seen_ns` — **memo only**, not arb |

`SYN_EXEC_SENT` / `SYN_EXEC_LAND` are declared in `syncrec.h` and **are not written by oneshot**.

---

## 6. Works / incomplete / disabled / experimental

### Works (in tree)

- OrbitFlare capture + `paper_orbit` follow (ops scripts exist).
- Frozen DLMM/Pump kernels + `cycle_size` → `opportunity_t`.
- Framing + generic trigger scan (TRIGGER-011 **detector** shipped; **verdict FAIL** for funded).
- Gate / `opp_synced` / `opp_searchable` journals.
- STATE-008 architecture (complete-deps + txn-coherent AUTH) — **code exists**; soak quality is **not** “done” (SCOREBOARD).
- EXEC-001–005 local proofs; EXEC-005A funded **memo** smoke.
- v0+ALT compile (`exec_v0`); Python simulate walk toward Custom(6).
- SWQOS client + racer + oneshot **machinery**.
- Hops plane publish **without** inventing RACE_READY.

### Incomplete

- Production send loop (continuous, not oneshot).
- Wiring `syncrec` SENT/LAND to live send.
- `paper_orbit` sign path: dummy blockhash, no SWQOS.
- Oneshot ↔ STATE-008 READY file.
- Audit `race_ready` vs plane `RACE_READY` unification.
- 3-hop / family-255 executor (STATE-007: first `would_send_new` had **no** 3-hop executor).
- TRIGGER-011 exact router N (Jupiter / 6Vo / DF1ow / FLASHX): **no invented S′**.
- TX-OVERLAY-001 / PUMP overlay: soak vs publication.
- PUMP-AUTH-016 gate: **0 unexplained Pump mismatches** — in progress (`soak_pump016_20260926`).
- `dlmm_orders` / STATE-011: **not in paper hot path** until soak ends (`arb-core/CMakeLists.txt`).

### Disabled / blocked

- `FUNDED` default 0 (C macro and Python env).
- Oneshot refuses without `FUNDED=1`.
- TRIGGER-011: funded blocked by ticket verdict.
- STATE tickets: “not armed.”
- `leader_send` must not become a public TPU client (`arb-exec/README.md`).

### Experimental / research-only

- `arb-nic` XDP / veth benches; physical NIC work stopped.
- Flowra, Rabbit, DoubleZero (not hot path).
- `arb-cap/v1_router`, `alpha_census`, `timer_decay`, `fam6`.
- `paper_live001`, `paper004`, `cap001`–`cap009` historical binaries.
- `program_dlmm2` superseded by `program_hops`.
- EXEC-LIVE-001: program written; **mainnet executable: no** at ticket time (wallet/deploy).
- Compile-time `FUNDED` sign in `paper_orbit`.

### Unverified from this checkout

- Whether Frankfurt currently has AUTH READY, RACE_READY templates, or a running `paper_orbit`.
- Whether OUR_EXEC `38dsYLgt…` is deployed and healthy **today** (`TOMORROW.md` / hops_live still name that id).
- Current hourly PnL (none in repo).

---

## 7. Historical / current metrics in artifacts

These are **snapshots of past runs**, not live dashboards.

### 7.1 STATE-007 funnel (30 min, plane READY) — `arb-cap/state007/STATE007.md`

```
actual-size > hurdle       2
old age32 pass             0
mut_authoritative pass     1
would_send_new             1   (877575 lamports, 3-hop, family=255, no ALT templates)
exec_fam (route0)          1   (2482975 lamports, pre-READY / not mut_auth)
```

Stream in **that** ticket: **0 account updates** (gRPC UNAUTHENTICATED). STATE-008 replaced the writer. Do not treat STATE-007 stream health as current.

### 7.2 STATE-008 FASTSOAK — `arb-cap/state008/SCOREBOARD.md`

Root: `/data/bsc/captures/soak_fastsoak_20260925/state008`  
SHADOW rows: **89938**  
exact: pump 245, dlmm 8714  
mismatch: pump 4117, dlmm 4272, unknown 72590  

Pump mismatches: **97.5% `virtual_reserve_config`** (first-dev problem).  
DLMM: volatility 52.1%, publication_ordering 20.5%, wrong_tx_association 18.1%.

### 7.3 Paper live (voided $)

`PAPER-LIVE-001`: 74.7M shreds → **599595** positive gross opps. Later **PAPER-002 FAIL** (quoted S_today vs prior-day shreds). Dollar funnels from that era are **void**.

`PAPER-004`: 34/113 OK positive; 72 `DLMM_MISSING_BIN`; **0/10** pred S′ = chain.

### 7.4 Frame / router

`FRAMEV1001.md`: historical winners framed **100%** after v1 parser (was 76.06%).  
`V1ROUTER001.md`: 589 v1 router winners; **`v1_symbolic_exact`: 0**.

### 7.5 SWQOS bench (`SWQOS_BENCH.md`)

Memo-only, Frankfurt. **WARM 200** attempts: `swqos_send==0` on **4**, first RPC seen **2**, confirmed **2**. This is **not** arb landing and shows submit/landing is not “solved” even for memos in that sample.

### 7.6 Oneshot / SCOREBOARD send counts

**No repo artifact gives a current chain of** `positive → prep → native_ready → policy_admitted → would_send → sent → landed` **as those names.**  
`would_send_new` **1** is the only carefully documented paper-send predicate hit in STATE-007. Funded arb **sent/landed counts for the searcher path are unverified here** (oneshot is one-shot and disarms).

Measure live with:

```bash
python3 arb-cap/oneshot/audit_funnel_window.py   # if audit path exists on box
python3 arb-cap/state007/agg_funnel007.py
python3 arb-cap/regress/scan_hour.py
```

---

## 8. Prioritized task list (second developer)

Increase **`positive → executable → would_send_new → (human-approved) sent`**. Do not optimize classify cycles, NIC, or new venues.

### P0 — See the funnel (1–2 days)

1. **Inventory live Frankfurt artifacts** (read-only): `opp_synced.jsonl`, gate lines, hops/alt plane JSON, `oneshot/RESULT.json`, process list (`paper_orbit`, `state008`, racer).  
2. **Instrument drop reasons** on the exec side: for every `opp_synced` / `would_send_new`, log why `framed_ready` or `size_gate` failed (missing plane, `race_ready==0` because ix-only, cap_ok, hurdle, cooldown, READY file). Prefer extending existing aggregators rather than new platforms.

### P1 — Executable coverage for route0 (the only funded shape)

3. **Resident templates** for every route0 pair that already prints `would_send_new` or fat `exec_fam` + `mut_authoritative`. `hops_live.py` stages: `inventory | deploy | sim7 | size | publish`. Custom(6) must be **real**; do not set `RACE_READY` by hand.  
4. **Align READY**: oneshot `S007_READY` vs STATE-008 READY — one file both sides trust, or document the alias. Do not fake READY.  
5. **Document and then code-check both RACE_READY meanings** before treating audit `race_ready==1` as plane-ready.

### P2 — Convert would_send_new that is not executable

6. **3-hop / family 255**: either a hops executor (`program_hops` / `hops_message`) that can actually send that shape, or **explicitly exclude** them from exec targeting so they do not look like “almost sent.” First STATE-007 `would_send_new` was this shape.  
7. **Tx size**: keep compiled v0 ≤ 1232; `hops_size_offline.py` / `size_ok`.  
8. **Missing ATAs / fee_recipient_quote**: plane `missing_ata` — control plane, not kernels.

### P3 — Send path quality (still no FUNDED without approval)

9. **Dry-run oneshot** (`FUNDED=0`) against historical `opp_synced` replay if you add a file follower that does not require EOF-only (today `follow_new` seeks EOF — live-only). A **safe replay harness** that never calls racer is acceptable.  
10. **Landing telemetry** into one jsonl: `swqos_rc`, `why`, race class — even for future sends.  
11. **Hurdle consistency**: decide whether paper `hops_hurdle_for_seq` or oneshot 525k is the send floor; do not silently use both.

### P4 — Only after human FUNDED approval

12. Arm scripts (`arm_oneshot6.sh`, `run_oneshot.sh`) with documented wallet, OUR_EXEC, plane snapshot, and abort conditions.  
13. One shot, then stop. No retry spray. No fee ladder (oneshot comment).

### Explicitly deprioritized

NIC/XDP, FPGA, new shred vendors, Pump kernel “cleanup,” universe expansion, market making, `dlmm_orders` in hot path, rewriting `classify_n`.

---

## 9. Acceptance criteria

| Task | Done when |
|------|-----------|
| P0 inventory | Written counts from **actual** files: `gate` rows, `gross_pos`, `would_send_new`, `opp_synced`, `tx_exact`, plane `vector_ready` / `RACE_READY`, oneshot RESULT if any. Gaps labeled unverified. |
| P0 instrument | Every skipped `opp_synced` in a test window has a **single reason enum** in a log/jsonl. Before/after counts on the same capture hour. |
| P1 templates | For N named route0 pairs: `tmpl0`+`tmpl1` present, `size_ok`, prior Custom(6) recorded, pool keys match `liveuniv`. `exec_v0` still passes. |
| P1 READY | Oneshot and AUTH writer agree on one READY path; oneshot still **refuses** if AUTH is not coherent. |
| P1 RACE_READY | A comment + test or checker: audit `tx_exact` ≠ plane Custom(6). No silent OR of the two. |
| P2 3-hop | Either a simulated hops tx for the STATE-007-shaped seq **or** funnel marks `exec_fam=0` as `not_v1_executable`. |
| P2 size | No published race template with raw > 1232. |
| P3 dry-run | Harness reports would-fire vs drop **without** `FUNDED=1` and without opening SWQOS. |
| P4 send | Human written approval; `FUNDED=1`; one RESULT.json; wallet delta explained; then `FUNDED=0`. |

---

## 10. Tests and commands after changes

All C trees: **Linux**. From each crate:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

### Must not regress (search frozen)

```bash
cd arb-core/build
./core003 && ./core005 && ./core006 --vectors ../tests/pump-vectors.txt
./core007 && ./core008
ctest --output-on-failure   # trigger011, alt_lifecycle
```

### Exec you touched

```bash
cd arb-exec && cmake --build build --target exec_v0 exec001 exec002 exec003
./build/exec_v0
# if you changed hops message / snapshot:
python3 tests/test_hops_message.py
python3 tests/test_route_snapshot.py
python3 tests/test_golden_hops.py
```

### Feed / AUTH consumer

```bash
cd arb-feed && cmake --build build --target paper_orbit
ctest --output-on-failure   # authpub_pred
```

### State / pump research (if you only consumed journals — still run if you touched shyft)

```bash
cd arb-state/shyft
python3 -m unittest test_authpub test_shadow test_overlay_n test_fastsoak
```

### Paper orbit (no send)

```bash
# on Frankfurt; does not send
export PAPER_SECONDS=60
bash arb-feed/scripts/paper_orbit.sh
```

### Oneshot — default must stay off

```bash
FUNDED=0 python3 arb-exec/scripts/oneshot_live.py
# expect: SEND=0 ... exit 0
```

**Do not** run `FUNDED=1`, `go_deploy.py`, `exec_swqos*`, or `arm_oneshot6.sh` unless a human explicitly asked.

---

## 11. Invariants and safety constraints

1. **`opportunity_t` is gross protocol profit only.** Exec adds fees/tips (`opportunity.h`, `ctrl.h`).
2. **`state_observe` / overlay S′ never write canonical S.** Only `hot_commit` / `state_refresh*`.
3. **Only `ST3_HEALTH_SYNCED` is sendable** (`state003.h`).
4. **Unknown CPI / unknown overlay mutation → fail closed.** No invented swap amounts (TRIGGER-011, `tx_overlay.h`).
5. **`quote == apply` on a copy.** Missing bin → fail closed. Do not “fix” quotes to increase send rate.
6. **AUTH predecessor is strictly before trigger N** (`authpub_pred`).
7. **IX_EXACT is not fundable.** Funded needs TX_EXACT + mut_authoritative + **route** RACE_READY (`paper_orbit.c` comment ~1804–1806). Code currently sets journal `race_ready` from TX_EXACT only.
8. **Publish never invents plane RACE_READY** (`hops_live.py`).
9. **Oneshot: never retries, no fee ladder, no nonce spray** (file header).
10. **Do not upgrade OUR_EXEC `38dsYLgt…` while ONESHOT#6 is armed** (`program_dlmm2/SUPERSEDED.md`).
11. **Never BPF Loader 2** (`6xfcHyCs…` dead — `TOMORROW.md`).
12. **`FUNDED` stays 0** unless a human says otherwise **in that request**.
13. **Do not silently resync shadow mismatches into success** (`STATE008.md`).
14. Frozen: `dlmm_apply_swap`, `dlmm_quote_exact_in`, `pump_apply_swap`, `pump_quote_exact_in`, `cycle_size`, `route0_process`/`route0_pack`, `route0_tx_compile`/`route0_tx_patch`, `route0_sign`, `nonce_claim`, AVX2 classify.

---

## 12. Files the second developer should avoid

Change only with first-dev coordination or a proven exec blocker:

- `arb-core/src/dex/*`, `cycle.c`, `hot.c`, `state003.c`, `state_apply.c`, `paper.c` (quoting)
- `arb-core/src/trigger.c`, `frame.c`, `classify_n.c`, `swapix.c` (except if a **layout** bug is proven)
- `arb-feed/src/tx_overlay.c`, `authpub.c` (prediction)
- `arb-state/shyft/state008.py`, `apply_n.py`, `overlay_n.py`, `shadow.py`
- `arb-cap/pump012/*`, `arb-cap/state008/*` reducers
- `arb-nic/**`
- Frozen exec: `route0.c`, `tx_template.c` offsets, `sign.c` message offsets, `nonce.c`

**Prefer:** `oneshot_live.py`, `exec_live002b.py` (plane/patch helpers), `hops_live.py` / `alt_plane.py` / `hops_*.py`, `route0_v0.c` only if v0 layout is the bug, `exec_swqos_racer.c`, `swqos/`, `audit_*.py` under `arb-cap/oneshot` and `state007`.

`paper_orbit.c`: touch **only** audit/exec-journal fields if required; do not retune prediction.

---

## 13. Technical debt and dangerous assumptions

1. **Two `race_ready`s.** Oneshot `framed_ready` uses **audit** `race_ready` (`tx_exact`) **and** plane membership. A tx_exact opp with no template is allowed through `framed_ready` only if the pool is in `_plane`. A plane-ready pool with ix-only overlay never becomes `framed_ready`.
2. **`would_send_new` ≠ executable ≠ will send.**
3. **Dummy `0xBB` blockhash** on C FUNDED sign — not a production send.
4. **Oneshot hardcoded paths** — other machines / this Windows clone will not run it as-is.
5. **`follow_new` EOF-only** — misses in-file history; one shot then disarm.
6. **50M frozen send vs optimal size** — can fail size_gate or send a worse clip.
7. **Hurdle 525k vs `hops_hurdle_for_seq`** — different floors.
8. **STATE-007 READY file** vs STATE-008 writer.
9. **STATE-007 ticket** documented unauthenticated gRPC; STATE-008 is the intended fix — **verify live**.
10. **SWQOS memo bench** landing rate was very low — do not assume ultrasend “just works.”
11. **PAPER-LIVE-001 counts are chronologically void** after PAPER-002.
12. **3-hop +EV is not V1-sendable** without hops executor.
13. **Pump virtual_reserve_config** dominates mismatches — sending on those quotes is economically unsafe.
14. **OrbitFlare rate** is not equivalent to a prior premium trial.
15. **Secrets** in `.env` / `~/.arb-*.env` — never log or commit.

---

## 14. Recommended first-week sequence

**Day 1 — Map, don’t code.** SSH (if you have access). Confirm processes. Copy one hour of `kind=gate` + `opp_synced`. Build the table: `gross_pos`, `cap_hurdle`, `mut_authoritative`, `would_send_new`, `exec_fam`, `tx_exact`, plane `RACE_READY`. Read this file + `arb-exec/README.md` + `oneshot_live.py` + `consider_framed` / `note_searchable`.

**Day 2 — Failure taxonomy.** Add/run an aggregator that attributes every `would_send_new` and every `opp_synced` to one drop bucket (§4). No kernel edits.

**Day 3–4 — Templates.** For the top route0 pairs in that hour, run hops/alt plane until `vector_ready` and recorded Custom(6). Do not invent RACE_READY. Keep `FUNDED=0`.

**Day 5 — READY + race_ready honesty.** Fix or document STATE-007 vs 008 READY. Write a checker that prints `tx_exact` vs plane flag side by side.

**Day 6 — Dry-run.** Offline would-send report. `exec_v0` + hops unit tests green. Show before/after coverage %.

**Day 7 — Review with first developer.** What is still prediction-blocked (overlay, Pump 016, TRIGGER-011) vs exec-blocked (templates, size, ATAs). **Do not arm FUNDED** this week unless the human owner explicitly orders a single oneshot.

---

## 15. Agent operating rules

These rules override “make it elegant” and “enable the feature to test it.”

1. **Inspect evidence first.** Read the functions and the jsonl/SCOREBOARD. Do not trust READMEs over code. Do not invent metrics (`native_ready`, etc.).
2. **Small targeted diffs.** One failure bucket per change. No tree-wide refactors. No “while I’m here” kernel cleanups.
3. **Instrument failure causes.** If a gate is silent, add a journal field or aggregator row. Unexplained drops are unfinished work.
4. **Benchmark before/after.** Same capture hour or same `opp_synced` window. Report: `would_send_new`, `tx_exact`, plane-ready intersection, dry-run would-fire.
5. **Preserve correctness.** Fail closed. Frozen math and frozen account order stay frozen. Prediction mismatches are not “noise to send through.”
6. **Avoid broad rewrites.** No new networking stack, no FPGA, no new feed, no new AMM, no merge of paper_orbit + oneshot into a rewrite.
7. **Never enable funded sending without explicit human approval in the user message.** Do not set `FUNDED=1`, do not run `arm_oneshot6.sh`, do not call `swqos_send` / racer with a real arb, do not deploy/upgrade OUR_EXEC, do not transfer SOL, do not put secrets in git or chat logs.
8. **If asked for both a send exploit/PoC and a fix:** provide the **fix/hardening only**.
9. **When blocked by prediction:** stop and list the ticket (`PUMPAUTH016`, `TXOVERLAY001`, `TRIGGER011`, SCOREBOARD class). Do not “approximate” S′.
10. **When blocked by missing Frankfurt state:** mark **unverified**; do not fabricate funnel rates.

---

## Quick file index for agents

| Need | Open |
|------|------|
| Funnel write | `arb-feed/src/paper_orbit.c` — `note_searchable`, `consider_framed`, `audit_opp_synced`, `write_gate` |
| Opportunity | `arb-core/include/opportunity.h`, `arb-core/src/hot.c`, `paper.c` |
| Send | `arb-exec/scripts/oneshot_live.py`, `exec_live002b.py` |
| Plane | `arb-exec/scripts/hops_live.py` `publish` |
| v0 layout | `arb-exec/include/route0_v0.h` |
| AUTH | `arb-state/shyft/state008.py`, `arb-feed/src/authpub.c` |
| Overlay | `arb-feed/src/tx_overlay.c` |
| Hurdles | `arb-core/include/hops_hurdle.h` |
| First-dev Pump | `arb-cap/pump012/PUMPAUTH016.md`, `PUMPOVERLAY016.md` |
| Do not fund | `arb-cap/trigger011/TRIGGER011.md`, every STATE `FUNDED=0` |

---

*Generated from the TheMoneyMaker tree. Live box state and current PnL: unverified.*
