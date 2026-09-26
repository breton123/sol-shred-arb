# Execution readiness

Read-only audit of the resident route0 plane on 2026-09-26. No SOL was moved, no ATA or lookup table was created, no plane was published, and nothing was sent. `FUNDED` was not set.

Unsigned `simulateTransaction` used `sigVerify: false` and `replaceRecentBlockhash: true`. The signature was zeroed. Amount in was the frozen 50000000 lamports. Minimum profit and the CU price were the oneshot wire values, 525000 and 800000. The templates still request a CU limit of 400000.

Plane rows with both templates: **72**. Unique DLMM pools: **48**. Unique Pump pools: **45**. Audit `RACE_READY` (template, ALT, current bank, ATA, and unsigned sim together): **4**.

The plane file's uppercase `RACE_READY` means both directions compiled and the ATAs existed when the plane was written. This report's `RACE_READY` requires Custom(6) or success on both directions as well.

## Coverage

| check | pass | what it means |
|---|---|---|
| TEMPLATE_VALID | 72 / 72 | static 11 keys, `ARBEXEC0`, writable 15/16, readonly 10, length 623/626, CU limit 400000 |
| ALT_VALID | 72 / 72 | lookup table active on chain and every index resolves |
| VECTOR_VALID | 60 / 72 | pool, mints, vaults, oracle, event authority, fee recipient, and the current active bin match the template |
| ATA_VALID | 72 / 72 | user WSOL, user base, and fee-recipient WSOL exist with the expected mint and owner |
| SIM_VALID | 4 / 72 | both directions return success or Custom(6) |
| RACE_READY | 4 / 72 | all five of the above |

## Programs

OUR_EXEC `38dsYLgtLkHKDMYNBemkEM3WkvZSUo3RvxZSm7eMDj4K` exists, is executable, and is owned by the upgradeable loader. Programdata `CVt6poAnrsq3ZtGbvB8tQ91kMtGqSjBydbGzpZxFfv7v` is 18757 bytes. The four routes that reached the profit guard failed with custom `0x6`. That is `ERR_PROFIT` in `arb-exec/program/src/lib.rs`. The ASCII bytes `ARBEXEC0` are not stored as a contiguous string in programdata. An 8-byte compare can compile to an immediate, so that search does not show a different program.

ARBHOPS0 on the box is `CnddPhKV1fnKE7ic5nSJcoVq2XFmQ9daE3tuqc2u6qTt`, executable, upgradeable loader, programdata `EQzZX9U6jeYGBdBS6Z5vk1oN4zAZ1SyGjrL1hThfUf9D`, 17181 bytes. The retained `hops.so` is 17136 bytes. The difference is 45, the upgradeable programdata header, so the deployed ELF is the same length as that binary. The ASCII bytes `ARBHOPS0` are absent from both, for the same immediate-compare reason. Route0 oneshot does not invoke ARBHOPS0. It invokes OUR_EXEC.

## Unsigned simulation

Each row has one failure reason. A later sim error is still listed when the first failing check was the vector.

| reason | routes |
|---|---|
| `SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']}` | 45 |
| `VECTOR_VALID:stale_active_bin` | 12 |
| `SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]}` | 7 |
| `RACE_READY` | 4 |
| `SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 6036}]}` | 3 |
| `SIM_VALID:dir1:{'InstructionError': [2, {'Custom': 6036}]}` | 1 |

Custom(6) on both directions, the profit-guard proof:

- DLMM `9xiLuqDSvN1pgyHSHCeRbrKFTe1DWbPAMJRm2usYgdaX` / Pump `2i2iULr7UwK1SDRB17T5FUtiMnFQL7fyy7rh69brZihc` / token `8k4sBtEeK4pf26noKqApv8NBTnuSJcbdwpKYknk5PbAA`. CU sell 121910, buy 135785. Raw 623 / 626. both pubkeys are unique.
- DLMM `8eLx26sto5xBSg8r1ksidtkmQyHzV2JUrQU97qmKw1Tq` / Pump `8R4DDi9X3RBLr876hhRJCv4Gvsy8d9SkABgb8YiHapo9` / token `J141JCiXKGcrhDCgWUTCL9qz7h943iCibNiLNfqZpump`. CU sell 127987, buy 136725. Raw 623 / 626. both pubkeys are unique.
- DLMM `E27r15wB77JfF1hFkfeqoP2ZyZHKMWKgZ9Aix2cdPAuq` / Pump `ASgoadVEDL8zJn6KLUiMSh9m8x2yYAEZPsUSpvxHj3LY` / token `AyYNfPtftg2zDP4ZbgcoQMggQtwLh4zpfVVmUJs2thto`. CU sell 116968, buy 130964. Raw 623 / 626. both pubkeys are unique.
- DLMM `E3SotafntrgRg9XjppxqoJWSR4GUaJV7sA8u4a89rYo6` / Pump `5PGhKctym6odbHGo2tKMST2AjmJsb2uZBQrKkn4ZuFT5` / token `Ge87EtsjwRQbHaqQmKRno69RFTwh9bfSsm99XNxTpump`. CU sell 119842, buy 133724. Raw 623 / 626. DLMM pubkey is shared with another Pump, so a journal of that DLMM does not send.

The other sim failures, after the template and the ALT resolved:

- **45** `IncorrectProgramId` on the sell instruction. 44 of those then return Pump custom 2006 (`0x7d6`) on the buy. One fails both directions with `IncorrectProgramId`. Vector and ATA checks passed, so the pool, vault, mint, and bin pubkeys match the current bank. The program id in the CPI does not match the owner of one of those accounts.
- **12** `stale_active_bin`. The current DLMM active bin array is not either bin account in the template. The sim returns DLMM custom 3005 (`0xbbd`), the anchor bin error already classified as a vector failure. ATAs on these 12 still match.
- **7** Pump custom 2006 (`0x7d6`) on both directions. The creator-authority PDA in the template matched. Another Pump account in the vector did not satisfy that program's seed constraint.
- **4** custom 6036 (`0x1794`). One of these passed Custom(6) on the sell and failed 6036 on the buy, so it is not `RACE_READY`. There is no local name for 6036.

No route failed the ALT parse. No route failed the ATA mint or owner check. No template failed the wire layout check.

## Account and vector failures

12 routes fail `VECTOR_VALID` with `stale_active_bin`. Refreshing those bin accounts means recompiling the plane. That path can extend lookup tables and create ATAs, so it was not run.

24 DLMM pubkeys are each used by two different Pump pools (48 rows). None of those pairs share the same Pump. `index_plane` and `load_race_plane` now mark a shared pubkey `plane_race_ready=0` (`ambiguous_pool`). File order no longer chooses which template a journaled pool sends. That refusal is in this checkout. The box keeps the previous oneshot until these scripts are copied over. Copying them does not move SOL. One sim-ready DLMM, `E3SotafntrgRg9XjppxqoJWSR4GUaJV7sA8u4a89rYo6`, is shared. Its Pump `5PGhKctym6odbHGo2tKMST2AjmJsb2uZBQrKkn4ZuFT5` is unique. A journal of the DLMM pubkey does not send. A journal of that Pump pubkey still resolves to this pair.

## ALT and ATA

All 4 lookup tables were active. The deactivation slot is the u64 at byte offset 4 and was `u64::MAX`. Addresses start at byte 56. Every writable and readonly index used by a template resolved.

All 72 routes have a user WSOL ATA owned by the template wallet, a user base ATA for that route's mint, and a fee-recipient WSOL ATA. That includes the 12 stale-bin routes.

## CU, size, and cost

Every instruction stream requests CU limit **400000**. Sell templates are **623** bytes. Buy templates are **626** bytes. None exceed 1232.

Solana bills the requested CU limit, not the consumed CU. Oneshot patches CU price **800000**. The wire cost is the same on every route0 send:

| component | lamports |
|---|---|
| signature | 5000 |
| 400000 CU * 800000 / 1e6 | 320000 |
| SWQOS | 150000 |
| safety | 50000 |
| **send floor** | **525000** |

Consumed CU from this audit is evidence of what the program used, not a new fee. The hurdle was not lowered.

| set | n | sell CU min | sell CU p50 | sell CU max | buy CU min | buy CU p50 | buy CU max |
|---|---|---|---|---|---|---|---|
| all templates | 72 | 20319 | 35449 | 146718 | 45701 | 45706 | 136725 |
| Custom(6) both dirs | 4 | 116968 | 121910 | 127987 | 130964 | 135785 | 136725 |
| IncorrectProgramId | 45 | 35030 | 35615 | 42546 | 45701 | 45701 | 65386 |
| stale bin / 3005 | 12 | 21931 | 21996 | 22069 | 45701 | 120520 | 126756 |
| Pump 2006 first | 7 | 76286 | 77536 | 77581 | 45888 | 45888 | 45888 |
| 6036 first | 4 | 20319 | 20618 | 146718 | 45712 | 114863 | 133754 |

## Gate audit

`exec_gates.py` and `oneshot_live.py` were checked for a path around the send conditions.

- `FUNDED` defaults to 0. `main` returns before the signer, the racer, RPC, `ensure_ata`, and `wrap_wsol`.
- The only READY file that can arm is `/home/louis/captures/state008/READY`. `AUTH_READY` pointing at state007 or any other path is refused on the funded branch. state007 READY does not arm.
- Journal `race_ready` (`tx_exact`) and plane `RACE_READY` are both required. They are not OR'd. Lowercase hops `race_ready` does not count.
- Gross must be greater than 525000. Equal to the floor does not send. `cap_ok` is required. Direction must be 0 or 1. A cooldown `SEND_BLOCKED` prefix does not send.
- When an opp row carries `seq`, `family`, or `n_hop`, `size_gate` now applies `v1_executable`. `dlmm-dlmm` and 3-hop return no send. Live `opp_synced` rows still do not carry those fields. A 3-hop or dlmm-dlmm journal whose pool pubkey is a unique route0 key can still reach the size gate. Closing that requires a journal field, which this side does not add.
- A pubkey shared by two DLMM/Pump pairs used to send whichever template was written last. Those keys are now `ambiguous_pool` and do not send.
- Plane uppercase `RACE_READY` is still not this audit's Custom(6) flag. Oneshot will send a unique plane key that failed the unsigned sim, if STATE is ready and the journal clears the other gates. The one shot has to be one of the unambiguous Custom(6) pools below. `prearm_check.py` fails unless at least one such pool exists.
- An authorized `FUNDED=1` process wraps 50000000 lamports of WSOL and may create the WSOL ATA before it tails the journal. That is the shot itself, not a path this audit ran.

## Per-route classification

| DLMM | Pump | template | alt | vector | ata | sim | race | failure |
|---|---|---|---|---|---|---|---|---|
| `ET9QEc18XnEXNyz8ZuGkJfgSuDDqLDiA1U8bEpyuyLKC` | `ENiVH49XwRM3Cu9n4Tp6CGynCFXf3Mz6CE3GRmVk1LH4` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `4MjpgAT7H8GmWsZDUaeGUNZwjur8n8sKCSPHHjQRE4sm` | `ENiVH49XwRM3Cu9n4Tp6CGynCFXf3Mz6CE3GRmVk1LH4` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `EAgJp7MzSydDWviEZbvdkuZjtJiy1sEukuV8GcSGxPt3` | `4kJEwCpiGtvFRxm1RKYExsFCm1CsB8RwnUQv3LCQs5YG` | yes | yes | yes | yes | no | no | SIM_VALID:dir1:{'InstructionError': [2, {'Custom': 6036}]} |
| `5u7PMsDxbaALbV9viti9Y4pEBVJqWSSp69uEsXGtiANq` | `4R8CiMnJWDNoes3fQi1ccPFJygPXazaHaWpHrN3rZeNj` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `CJab6RE2KNdhCLdY9sBxpijxpFegduaFg83UtEehLPh9` | `4R8CiMnJWDNoes3fQi1ccPFJygPXazaHaWpHrN3rZeNj` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `Gc5hVCBydc6k3Z7oc2cQEW4GThFQi2Fqk5HfKABqa2q8` | `6e3jZLtf4tQbWZm3f7A66jF8tfZn6MRQVrbDFgcNWarA` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `B3Me7MhVX5XPb4UHpnvYiac8KaTu26uxPzi36GksoUL9` | `8qwgwpdfbBMNhdG76bDmtvLeSqtG9cEwuGGy6wGKhTB9` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `2RX1ZogEMsjv1YjMF3m5U1DN7gVCtSLaQHs27F17ECve` | `FDrY5i5kuadZ1ik8gPS26qjj9Rw9mpufXMegGC2HNSP7` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `9xiLuqDSvN1pgyHSHCeRbrKFTe1DWbPAMJRm2usYgdaX` | `2i2iULr7UwK1SDRB17T5FUtiMnFQL7fyy7rh69brZihc` | yes | yes | yes | yes | yes | yes |  |
| `8ztFxjFPfVUtEf4SLSapcFj8GW2dxyUA9no2bLPq7H7V` | `7K7U6AUvgJH52ShbNrBcZae1zoGbZz7yay1P89Es5woX` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `8ztFxjFPfVUtEf4SLSapcFj8GW2dxyUA9no2bLPq7H7V` | `Abaakv6c8ra8pSGiTmV4BYHmxfLsdjoMNz51UGdWLie4` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `BBXyTX5UfbASibLRo3iaptuwF5846njxm7M4xFQTQz3d` | `7K7U6AUvgJH52ShbNrBcZae1zoGbZz7yay1P89Es5woX` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `BBXyTX5UfbASibLRo3iaptuwF5846njxm7M4xFQTQz3d` | `Abaakv6c8ra8pSGiTmV4BYHmxfLsdjoMNz51UGdWLie4` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `C8Gr6AUuq9hEdSYJzoEpNcdjpojPZwqG5MtQbeouNNwg` | `43PW2g6CPCtKvdBCsCuDUuztNFGo4xb6qeRUeZP6tZnX` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `C8Gr6AUuq9hEdSYJzoEpNcdjpojPZwqG5MtQbeouNNwg` | `5GVBaRJy2r5T3ccY3D4jLBJm12wHrxDCNyUfe62FipyS` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `Eio6hAieGTAmKgfvbEfbnXke6o5kfEd74tqHm2Z9SFjf` | `43PW2g6CPCtKvdBCsCuDUuztNFGo4xb6qeRUeZP6tZnX` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `Eio6hAieGTAmKgfvbEfbnXke6o5kfEd74tqHm2Z9SFjf` | `5GVBaRJy2r5T3ccY3D4jLBJm12wHrxDCNyUfe62FipyS` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `HdsFGjjY46twFKjqHqUyT2bnRS4XCo1HaExts5CSNprU` | `43PW2g6CPCtKvdBCsCuDUuztNFGo4xb6qeRUeZP6tZnX` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `HdsFGjjY46twFKjqHqUyT2bnRS4XCo1HaExts5CSNprU` | `5GVBaRJy2r5T3ccY3D4jLBJm12wHrxDCNyUfe62FipyS` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `2QDGj5BWMSNyEfmyDFx7eEvWWm4KujUPJ38Xdkntvxtd` | `VJf32Y1CFnaeHhaPnEEspP7T9AyYTYadx1WBbxkx4KQ` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `2QDGj5BWMSNyEfmyDFx7eEvWWm4KujUPJ38Xdkntvxtd` | `rrD9TypT3ft7wdCuMhaZ4RzvwJ14LLpEjVMMfKDTVQU` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `EtPcWELeHvrwaUwESUJTtvSAtmJS4DRbqtzMcY82s58J` | `VJf32Y1CFnaeHhaPnEEspP7T9AyYTYadx1WBbxkx4KQ` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `EtPcWELeHvrwaUwESUJTtvSAtmJS4DRbqtzMcY82s58J` | `rrD9TypT3ft7wdCuMhaZ4RzvwJ14LLpEjVMMfKDTVQU` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `HbjYfcWZBjCBYTJpZkLGxqArVmZVu3mQcRudb6Wg1sVh` | `VJf32Y1CFnaeHhaPnEEspP7T9AyYTYadx1WBbxkx4KQ` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `HbjYfcWZBjCBYTJpZkLGxqArVmZVu3mQcRudb6Wg1sVh` | `rrD9TypT3ft7wdCuMhaZ4RzvwJ14LLpEjVMMfKDTVQU` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `Hz1EtXTGaFEtAWRgRNpDMFV6vnSZtQUY9UqmdM6vfKSS` | `5v9QsXPMqdtN3VmUdG4psCaSUyh3p2AMXBMGA1ALQGaK` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 6036}]} |
| `HDhWhQCBrSh9xNWmNtsTi86eWj3yCoEiaRodjgNydo1b` | `5v9QsXPMqdtN3VmUdG4psCaSUyh3p2AMXBMGA1ALQGaK` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 6036}]} |
| `H2USRSaWuUchkbdmSJgKNfAm7ocyD4ZnCm69oRGyecKw` | `5v9QsXPMqdtN3VmUdG4psCaSUyh3p2AMXBMGA1ALQGaK` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `4kdxjt8pKEW4qV4ji4HANixwswDJw3Egn8L4x2BEWQqT` | `Mah2d8pT3w5JfBt7AqZLeFBF5tfgdDWAHmJoQdLwLzX` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `4kdxjt8pKEW4qV4ji4HANixwswDJw3Egn8L4x2BEWQqT` | `9XL3m3Aj1drrcS1v95uUPzntUzJdsCpPUDezeXd2ueon` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `GYqytuXSiX3GaPuCkLMY4jeRR3mAtyAuQqhD32d45g5y` | `2kYQVpASZDhozveWrB3YPYocqUY7LESXFNsKkznv1E2j` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `GYqytuXSiX3GaPuCkLMY4jeRR3mAtyAuQqhD32d45g5y` | `8kfZkZw1MTmxoTDzPTdGL31Ed193aYPFa3nwS1AKhYEE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `3sVrUSPny3dHukHuBeivBp87rqGQ8heBdHA48iZEDmwG` | `2kYQVpASZDhozveWrB3YPYocqUY7LESXFNsKkznv1E2j` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `3sVrUSPny3dHukHuBeivBp87rqGQ8heBdHA48iZEDmwG` | `8kfZkZw1MTmxoTDzPTdGL31Ed193aYPFa3nwS1AKhYEE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `AsSyvUnbfaZJPRrNh3kUuvZTeHKoMVWEoHz86f4Q5D9x` | `2kYQVpASZDhozveWrB3YPYocqUY7LESXFNsKkznv1E2j` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `AsSyvUnbfaZJPRrNh3kUuvZTeHKoMVWEoHz86f4Q5D9x` | `8kfZkZw1MTmxoTDzPTdGL31Ed193aYPFa3nwS1AKhYEE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `FzA8Fji7xdr9jfN7Y2YCUGLYwBzqP1eicKA4dX4m8BJg` | `2kYQVpASZDhozveWrB3YPYocqUY7LESXFNsKkznv1E2j` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `FzA8Fji7xdr9jfN7Y2YCUGLYwBzqP1eicKA4dX4m8BJg` | `8kfZkZw1MTmxoTDzPTdGL31Ed193aYPFa3nwS1AKhYEE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `6e7V9eegCHw997T72MxgwwJipZ6GJyZF8NvjkzT1rvpN` | `FnzKY6x7entQ1eR3D225dQyT7ybfka4PskBMQhb8L3CC` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `CFC6n181TdaxSZWNxYH5MmoLsVAf2V94bzWSbdhu8TgH` | `7czW7oGc1Rs7i18Rt2xdL9EKGxPukNmMhi7VdDTwjQaE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `CFC6n181TdaxSZWNxYH5MmoLsVAf2V94bzWSbdhu8TgH` | `GbyTnKNoSbBEuTt3W4ZKPjCNaFaFTRjYPNDVB1Cf8m8P` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `9JivMChLZWRk7bKf89cFLXfnXeEMqsPrgdHHymfS7Vcm` | `7czW7oGc1Rs7i18Rt2xdL9EKGxPukNmMhi7VdDTwjQaE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `9JivMChLZWRk7bKf89cFLXfnXeEMqsPrgdHHymfS7Vcm` | `GbyTnKNoSbBEuTt3W4ZKPjCNaFaFTRjYPNDVB1Cf8m8P` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `BCv5Ggg5563AYfkrErdXok2hKfjgUNtQ1A4yKuNbTjQ9` | `7czW7oGc1Rs7i18Rt2xdL9EKGxPukNmMhi7VdDTwjQaE` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `BCv5Ggg5563AYfkrErdXok2hKfjgUNtQ1A4yKuNbTjQ9` | `GbyTnKNoSbBEuTt3W4ZKPjCNaFaFTRjYPNDVB1Cf8m8P` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `J8a3ZKcDZA8HSinuCyjJggU8hnDgwkZKmwH8qDZ9nUcY` | `C2TadtxCNNowWioMpcAYPcgscMsJhuH4FHkzfBAh37yZ` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `46CgAPEz8V2e9UL5PDa3JNWFW6sk7uFCj7TjdB3XbKD3` | `8SryA3Vw8bCiPqPpqvWyQjCMRxcZEJGoGtqKeYCferfm` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `81GpCm4d13y8TozYtThabuSCLQN2o3bbrvDogXFPn8sA` | `8SryA3Vw8bCiPqPpqvWyQjCMRxcZEJGoGtqKeYCferfm` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `9PYge8aBV119HoFWm8HBvaaSqPvJpu2kUwMV9imRnPAx` | `BRjMA8UALNp3diTKHfdeAn5riQrYPoaYez7KhYWD4oEs` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `92J3X46dbnoPs25Vc3fr5m1xt9GVrQddqiPD9uzXQHH` | `2TtUS5ADKUkmsnj4wNygN9zxMDh8XewKoyC8jLBGLvuR` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `92J3X46dbnoPs25Vc3fr5m1xt9GVrQddqiPD9uzXQHH` | `4ka8BrmspaG6oPoCrLy7q9yJ2X9aUW2JbVfAESA2cYia` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `2gXV31km1F58FVFrwvjVKkLisWPnoGP6MNAiNWbp3MZn` | `3dcwhqJp6JBTJPq8ga335HWgSQVS7uQmdmeX7iGjMNpj` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `A3N64gxHQL8b2cQ75JM3nVqoRFYWmntaEUFfDmhYe1Nv` | `RA1HTmQgmA35zp35EfcktrF9sKVh4m5x6qSD788BWhA` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `A3N64gxHQL8b2cQ75JM3nVqoRFYWmntaEUFfDmhYe1Nv` | `Tyo8Q92Ge5YjGGZZtmV1FgwEqFJEY3UgEpEUQHjvTVG` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `8eLx26sto5xBSg8r1ksidtkmQyHzV2JUrQU97qmKw1Tq` | `8R4DDi9X3RBLr876hhRJCv4Gvsy8d9SkABgb8YiHapo9` | yes | yes | yes | yes | yes | yes |  |
| `Cqc2v6yhK5NBgmhNoYBFYmUA5WR1UriYANa3wf7ijN7C` | `7mETms4aUreNwHSL6ZnXntWw8cGiBTcNjHKm1o159tSQ` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `Cqc2v6yhK5NBgmhNoYBFYmUA5WR1UriYANa3wf7ijN7C` | `FbRpnhQjeGpNW2e9JMQyJwxg6ei6hnUNAbrdzso1Gwhy` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `BhjvwZoCir2jqVrdGemebDFmTeMW3eENFrxYffkPfj1Y` | `ECE2mWMQZUa8i8qGchuSAB66QzDN3WUhhtGRMbgNL3L` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `BhjvwZoCir2jqVrdGemebDFmTeMW3eENFrxYffkPfj1Y` | `2JSLMHVjeBsx7vzbAuwJnBtBqoPzdmz2uMWkt4d524Gc` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `6wJ7W3oHj7ex6MVFp2o26NSof3aey7U8Brs8E371WCXA` | `ECE2mWMQZUa8i8qGchuSAB66QzDN3WUhhtGRMbgNL3L` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `6wJ7W3oHj7ex6MVFp2o26NSof3aey7U8Brs8E371WCXA` | `2JSLMHVjeBsx7vzbAuwJnBtBqoPzdmz2uMWkt4d524Gc` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `EgGACLzNtvTWfjWopkMbbcRsUPAaSCcgPjbNqUCcLUCJ` | `5tYFviFWQRKV9BJSTHGitbdqEYC1BGUgRUDnSADUXqJP` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `E27r15wB77JfF1hFkfeqoP2ZyZHKMWKgZ9Aix2cdPAuq` | `ASgoadVEDL8zJn6KLUiMSh9m8x2yYAEZPsUSpvxHj3LY` | yes | yes | yes | yes | yes | yes |  |
| `71HuFmuYAFEFUna2x2R4HJjrFNQHGuagW3gUMFToL9tk` | `MRPEumEGYq184Uq4TrmEpz1W7Usmb64BHBt4mSUBPFc` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `71HuFmuYAFEFUna2x2R4HJjrFNQHGuagW3gUMFToL9tk` | `WuKc2iHwWoSbnRocxTLju3Z1kyzseXWuzWzz7ap2mHN` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `E3SotafntrgRg9XjppxqoJWSR4GUaJV7sA8u4a89rYo6` | `5PGhKctym6odbHGo2tKMST2AjmJsb2uZBQrKkn4ZuFT5` | yes | yes | yes | yes | yes | yes | RACE_READY; dlmm pubkey shared, journal of that dlmm does not send |
| `E3SotafntrgRg9XjppxqoJWSR4GUaJV7sA8u4a89rYo6` | `88KwfNjZBsatA3RmVteGV1uqzm3up4ZiQxYSiFjPsiUD` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 2006}]} |
| `FcgMfW5UTrgviQWABgrTaYYHrb2gBhH98Y3KVE7ujk8m` | `GExyM2egh9WbZhDe1r7q44mJET8xbPTnnKTc2rx2usWG` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `FRzLWC7LPGAAgDeuWXn7gEwpMyueDe5XN7eAU7fGu2Qz` | `Ftjga524YrS7RPzGCcezMuQnFDYa8PcvWDY5mFmZk5dy` | yes | yes | no | yes | no | no | VECTOR_VALID:stale_active_bin |
| `GLGMQ2TUh5D5mLpZDYezovkDAeoAkZbe8f7VRtDu9Coy` | `AatUCcoFPRovvTrSLUzN8yfjuvnQHfVoThKQiyfsHvEr` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, {'Custom': 6036}]} |
| `EbLiu3GfBYh9cfxrdrfhQgbZJmXqch38NmzZKZSkFGGq` | `4WEdWCofCQccncy68TMkdsk4vnQuJB7EVkTdC813FuYN` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |
| `EbLiu3GfBYh9cfxrdrfhQgbZJmXqch38NmzZKZSkFGGq` | `DN8efewWeSkkFCffjZBgBYvfVJ9EasTKgmxf4FqA8Xf5` | yes | yes | yes | yes | no | no | SIM_VALID:dir0:{'InstructionError': [2, 'IncorrectProgramId']} |

## Remaining blockers

- `/home/louis/captures/state008/READY` is absent. AUTH is not coherent. Oneshot refuses. This is state work, not a template gap.
- 68 of 72 pairs are not unsigned-sim ready: 45 `IncorrectProgramId`, 12 stale bins, 7 Pump 2006, 4 custom 6036. Fixing bins or the token-program account means a plane rebuild, which can spend SOL. It was not done. Those pairs are not the one shot.
- 24 DLMM pubkeys are ambiguous. They do not send. One sim-ready pair is affected on its DLMM key only.
- `paper_orbit` was not started by this audit. After STATE is coherent, a live journal still has to produce `tx_exact` on one of the three unambiguous pools, with `cap_gross` above 525000.
- `opp_synced` has no `seq` or `family`. The v1 shape filter runs only when those fields are present.

## One funded shot

All of the following, and a human has to say so in that request. This file is not that request.

1. `python arb-cap/exec_v1/prearm_check.py` is run on the Frankfurt box, with this checkout's `template_audit.json` beside it, and exits 0. It prints every gate. It does not set `FUNDED`, arm, or send. A run off the box cannot see the READY file, the plane, or the racer socket, and exits nonzero for that reason.
2. `/home/louis/captures/state008/READY` exists because the STATE-008 writer is coherent. `state007/READY` does not count. `AUTH_READY` must be unset or that exact path.
3. The journaled pool is one of these pairs. Both pubkeys are unique, and this audit marked the pair `RACE_READY` with Custom(6) on both directions:
   - DLMM `9xiLuqDSvN1pgyHSHCeRbrKFTe1DWbPAMJRm2usYgdaX` / Pump `2i2iULr7UwK1SDRB17T5FUtiMnFQL7fyy7rh69brZihc` / token `8k4sBtEeK4pf26noKqApv8NBTnuSJcbdwpKYknk5PbAA`
   - DLMM `8eLx26sto5xBSg8r1ksidtkmQyHzV2JUrQU97qmKw1Tq` / Pump `8R4DDi9X3RBLr876hhRJCv4Gvsy8d9SkABgb8YiHapo9` / token `J141JCiXKGcrhDCgWUTCL9qz7h943iCibNiLNfqZpump`
   - DLMM `E27r15wB77JfF1hFkfeqoP2ZyZHKMWKgZ9Aix2cdPAuq` / Pump `ASgoadVEDL8zJn6KLUiMSh9m8x2yYAEZPsUSpvxHj3LY` / token `AyYNfPtftg2zDP4ZbgcoQMggQtwLh4zpfVVmUJs2thto`
4. That row is `framed`, journal `race_ready` is 1 (`tx_exact`), the plane row is uppercase `RACE_READY` with both templates, `cap_ok` is set, and `cap_gross` is greater than 525000. The sequence is `dlmm-pump` or `pump-dlmm`.
5. `COOLDOWN.json` does not have `SEND_BLOCKED` on that pool. `ARMED` does not already exist. The racer socket exists. The wallet can cover the 50000000 wrap plus fees.
6. One `FUNDED=1` `oneshot_live.py`, then back to 0. No retry and no fee ladder. That process wraps WSOL before it waits. That wrap is the authorized shot, not a step to run now.

`E3SotafntrgRg9XjppxqoJWSR4GUaJV7sA8u4a89rYo6` also returned Custom(6) on both directions. Its DLMM pubkey is shared, so it is not in the shot list.

Until STATE-008 is coherent, `prearm_check.py` exits nonzero. Nothing in this audit arms a send.
