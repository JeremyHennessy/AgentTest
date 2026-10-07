# Ora first copied-policy comparison: invalid, attempt consumed

The 7 October 2026 attempt ended with an **invalid scientific result**, native exit code **2**, and terminal reason `scientific_call_counts_unknown`. It cannot answer the preregistered retained-versus-withheld benefit question or establish whether Ora generally learns. An unclosed transition leaves final whole-run accounting unknown; the complete study index, raw evidence seal and scorer report were never produced. Invalid accounting takes precedence over incomplete, adverse, coverage and benefit classifications.

This report freezes the existing evidence before any repair or new study. The single attempt is consumed. It authorizes no retry, resumption, replacement case or new-world activation.

## Identity and terminal evidence

The run is `ora-v4-first-comparison-2026-10-07-once`, with run ID `ora-two-decision-v4-first-comparison`. It used the separately reviewed enabling-only derivative of scientific implementation **v3**. The preregistered protocol remains **V4**, SHA-256 `0764aab03b99d59cc9eeb9c3aaeac481beda5c955c860e6c3db5f94fd08bda50`; its conditions, budgets and acceptance criteria did not change.

The publication base is [draft #225](https://github.com/JeremyHennessy/AgentTest/pull/225) at immutable head [bdffe5b](https://github.com/JeremyHennessy/AgentTest/tree/bdffe5baa513050cc94c11fbe0d41523d1038fb7). Its default-off source checkpoint remains unchanged. The earlier source-only checkpoint descriptions are historical: this separate report records the later, consumed execution. The three green exact-head CI runs establish software-check status only, not a scientific result; no CI was dispatched for this report.

The [byte-exact external exit receipt](evidence/ACTUAL_NATIVE_EXIT_RECEIPT.json) records native exec session `8327` returning exit code 2, observed at **09:15:03 UTC** in tool chunk `a77023`. The native prepared-before-exit status alone is not treated as proof of exit. The controller was reaped, whole-group termination was attempted, `cleanup_error` was 0, and `restarts` was 0.

## What the saved prefix establishes

The [integrity audit](evidence/ACTUAL_RUN_INTEGRITY_AUDIT.json) verifies one intact **15,293-record** chain. All **222** dispatched workers have matching source receipts; **221** completed. It finds no repeated worker or transition slot, source mismatch or observed counter overrun.

- **16 of 32** scheduled pairs have complete exports. A partial seventeenth pair has both second decisions and common probes. Layouts 1 and 2 each have eight complete pairs; layout 3 has the partial pair; layout 4 has no policy pair.
- **68** durable nonnull decisions and **390** durable transitions are preserved: 256 neutral, 66 owned and 68 probe transitions. The ledger contains **391 transition-entry observations**. These observed prefix counts do not replace the unknown final whole-run counters.
- The unclosed entry belongs to `layout3.t32.R.execute.stage2`, call 22, ledger sequence 15291. It has no recorded return or durable outcome. The corresponding W second execution did not start.
- The [saved-pair audit](evidence/SAVED_SCIENTIFIC_RESULT_AUDIT.json) confirms matched first inputs, decisions and lifecycles, correct E1-only retained/withheld masks and posterior relationships, and agreement between completed second owned outcomes and their common probes. These checks cover only the available pairs.

The final [independent audit](evidence/FINAL_ONE_ATTEMPT_AUDIT.json) accepts preservation of this invalid result. Its per-action and per-anchor arithmetic is descriptive partial evidence only. No full-study efficacy percentage, benefit score, learning conclusion or readiness claim is reported.

## Measured resources and limits of attribution

| Saved observation | Value and scope |
| --- | --- |
| Wall-clock snapshot | 848.012239470 seconds from the native window start to its last prepared snapshot |
| Aggregate CPU snapshot | 846.269951 seconds, under the reviewed singleton-CPU lifetime composition |
| Internal supervision window | 850 seconds; the work-stop boundary reserves the final 2 seconds |
| Run-owned logical output | 21,066,119 bytes, including the 630-byte permanent marker; 310 files inside the raw run root |
| Process address-space composition | Fixed 32/96/384 MiB allocations, totaling 512 MiB; this is source-bound enforcement evidence |
| Measured peak RSS | Not available |

The resource observations precede actual exit; they are neither an exact self-observed exit timestamp nor a measured peak-memory result. The saved evidence locates the interruption at the work-stop boundary with one unclosed owned transition. It does not, by itself, apportion runtime cost among checking, process startup, policy work or other operations. This report identifies no performance defect or repair. Enforcement claims assume the reviewed source and ordinary working Linux kernel/process semantics, without a hard real-time or power-loss guarantee.

## Preservation and verification

[Preservation references](evidence/PRESERVATION_REFERENCES.json) bind the executed binary, module manifest, profile, protocol, immutable source commits and the two separately retained archives. The raw-evidence archive is **15,075,349 bytes**, SHA-256 `d17384d03a43465ac90fefa368ecbf8c0ffee959268b045531af84e91937dd45`; the catalog archive is **53,544 bytes**, SHA-256 `8afed079ce8aea691ada08436518bfe60d4f2a41f684b14a429dc6a4ea3c4bce`. They preserve 425 files, including all 310 raw run files and the complete captured source/runtime closure. The preservation receipt verifies archive members and unchanged original bytes and metadata. This is checksum-backed preservation, not a remote immutability guarantee.

The four execution/audit JSON files here are byte-exact copies; [SHA256SUMS](SHA256SUMS) covers all report additions except itself. Review and report preparation used saved-file reads, parsing and hashing only. No native/API/world/policy execution, replay, simulation, test run, CI dispatch or source modification occurred during report preparation. No missing output was filled. The lost historical six-call raw archive remains unavailable and is not represented as recovered by this preservation package.
