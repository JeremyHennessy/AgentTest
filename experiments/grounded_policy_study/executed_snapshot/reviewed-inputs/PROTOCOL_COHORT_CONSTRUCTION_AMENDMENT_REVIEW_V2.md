# Prospective cohort and dispatch amendment review, version 2

2026-10-07. Read-only causal/source review and arithmetic derivation. Zero simulator calls, project imports, API reruns or edits to policy-work. This memo proposes a future protocol amendment; it does not authorize scientific execution.

## Decision and version history

**Recommend the explicit prospective amendment below, preserving the frozen API.** Combining creation and the first T1 in one fresh worker preserves the intended evidence contrast if both arms' logical input copies are frozen first, each constructed cohort matches its immutable layout reference before its own T1, and both first T1 receipts are committed and compared before either owned action.

This is a real ordering change as well as an invocation-count change. The original protocol requires creating both capsules before first-stage T1; this proposal permits the first capsule's T1 before the second capsule exists. Do not describe that ordering as already authorized by the original freeze.

Version 1 is preserved unchanged at `PROTOCOL_COHORT_CONSTRUCTION_AMENDMENT_REVIEW.md`, SHA-256 `6594cea842a20396c3edf4d4ef911011986c986d9495b2df23ed3411151a6790`. It proposed separate create and first-T1 workers. Its 448-worker / 2,114-validation / 4,614-reconstruction schedule is superseded **only prospectively** by this version's combined schedule. It must not remain an active competing adapter specification.

The original `FIRST_COMPARISON.md` remains unchanged, SHA-256 `6f40f7bd8606a0e97f3f18eb4220347309e36892c0872bd4f5ff2721c6881241`. Adopt a new named protocol/amendment with its own hash and review record before producing any scientific stream. The tested API's earlier GO and the scientific run's NO-GO remain unchanged.

## Why the contrast is preserved

The frozen generator is deterministic and receives only D. It cannot inspect U, E1, current anchor context, other capsules, run/path labels, elapsed time or a random generator. Repeating construction from identical D/code produces identical complete model definitions. No first-owned outcome exists when either first T1 is selected. Both first forecasts and selected commands remain durably committed before any first actuation, and exact paired equality is checked at that point.

The first arm may therefore complete create/T1 before the second arm's creation without receiving extra evidence or changing the second arm's inputs. This ordering saves one worker startup per capsule. It does not change the first actions, the matched T3 lifecycle or the later E1-only updater mask. Any late cohort mismatch invalidates and stops the entire run; earlier apparently favourable data cannot survive as a partial effectiveness result.

The phrase “all 16 copies match before any dependent T1” is replaced with a per-copy requirement: **each actual capsule must match the immutable reference before its own T1**. Future anchor copies need not exist yet. A completed run still must have all 16 matching copies per layout. There is no waiting barrier holding two live workers, no replacement reference and no selection among differing cohorts.

## Exact frozen source basis

- `executive.py` SHA-256 `9c64e551de6c9cf1c9b549acae223c32cd85ce079a704a91089dd32ced6af1f9`.
- `policy.py` SHA-256 `42ba90338c37caf906630431a50477087e24ca965f0515d6850b81ab3f614a5a`.
- `store.py` SHA-256 `3be6dc4e4dae86494b9f0d86210d4a1b7c0fd5d1648cf7ba17fdb08fbbb80493`.

`create` invokes `build_cohort(D)` at executive.py:266, before the output lock/existence check. It performs a write validation and returns a new object whose constructor reads/validates the capsule. A subsequent explicit read adds another validation. Each successful `select_next`, `execute` or `interpret` has one pre-read and one pre-write validation. Every capsule validation independently reconstructs D once through `verify_cohort`, and once more for each of its zero, one or two retained decisions through `verify_evaluation` (executive.py:180–198; policy.py:547–556; store.py:127–159).

An attempted recreate can invoke the producer even when the output already exists. Consequently the global budget must constrain admitted create entries, not only successful creations. The API itself is not changed or monkeypatched to achieve this schedule.

## Replacement text for the prospective protocol

The following replaces all affected D/construction, paired-initialization and dispatch wording. Existing later-stage masking, scoring, endpoint, eligibility and stopping rules remain in force unless expressly changed below.

### 1. Replace the D bullet at original lines 48–49

“D is the initial observation and neutral transitions 1–32, fixed once per layout. Seal the complete canonical D frames and projected movement rows before any dependent capsule creation. Each of the 16 pre-registered arm capsules for that layout constructs its cohort exactly once through the frozen ordinary create API. The first declared retain-first capsule at the earliest declared anchor supplies the immutable reference cohort; this is a real study capsule, not an extra build. Its complete D/cohort bytes and digest are durably sealed before its own first T1. Every later copy must equal the same sealed D/cohort before that copy's own first T1. Future anchor copies need not exist yet. A completed run has four layout-indexed immutable cohort definitions, 16 matching copies per layout and 64 producer constructions. U, E1, current anchor context and later/evaluator outcomes never generate, revise or select among cohort definitions.”

### 2. Replace paired initialization at original lines 73–86 and step 1 at lines 88–91

“Before either arm's initial worker starts at an anchor, register both arm-case slots and fixed evidence modes, reserve their distinct output/source destinations, and prepare and verify their two separate source-file sets. Both sets must contain byte-identical logical initial copied Ora state, copied world and complete verified public prefix, with identical D/U, discovery boundary, initial observation, code/runtime/configuration and budgets. Freeze those inputs before either creation; the first worker cannot alter the second arm's input set.

“Actual native run UUID and filesystem/lock identities are minted by the ordinary create API. Bind each returned native identity to its pre-registered slot exactly once immediately after create and before its T1; do not claim those uncreated native identities were preassigned or weaken their validation. Run/path/inode differences remain provenance only and cannot enter policy calculations.

“Use serial cold initial workers in fixed retain-first then withhold-first order. Each worker calls create, explicitly reads its created capsule, completes the durable D/cohort reference seal-or-equality handshake, selects first T1 once using the current CAS revision, and reads the saved proof once. The first arm may therefore commit T1 before the second capsule is created. A missing/failed first reference is terminal; no later capsule replaces it. The reference handshake performs byte/hash identity checks on the returned saved data, not another generator/API read or selection.

“Neither initial worker executes an owned action. After both workers exit, compare the saved first logical inputs, complete forecast/menu, admitted cases and selected command/owner semantics, with only declared run-local provenance separated. Both first T1 receipts must be durably committed and equal up to their authorized per-run identifiers before either E1 action. A discrepancy is invalid and terminal. At that point both independent capsules exist, and the existing cold-restart execute/T3 sequence proceeds. Full actual histories are retained, and the later E1-only updater intervention is unchanged.”

This explicitly supersedes the original requirement that both capsules be created before either first T1. It does **not** permit an outcome before the other arm's first T1, sharing capsule state, altering inputs after seeing the other selection, or a concurrently live waiting barrier.

### 3. Replace the construction budget at original lines 297–299

“Model production: exactly 64 deterministic build_cohort(D) invocations on a complete run, one per pre-registered arm capsule and 16 per layout; at most 64 on any run. No extra four canonical builds, producer preflights, create retries, replacement cases or alternate references are allowed. Every copy keeps the existing 128 supported-conditionals-per-action ceiling and at most seven concrete retained rules plus N. Four layout-indexed cohort definitions remain immutable and exactly identical within each layout. Independent proof-checker reconstructions are separately bounded and counted; they are not additional learned cohorts, generator producer invocations, selecting-backend calls or simulator transitions.”

### 4. Add one authoritative bounded worker/checker schedule

“For each capsule the initial cold worker performs exactly create -> explicit read -> durable reference seal/equality handshake -> select_next -> explicit read. No extra API operation occurs inside the handshake. Each remaining non-null stage uses a new cold worker: stage-one execute, stage-one interpret, stage-two select, stage-two execute and stage-two interpret. Each such worker performs constructor/implicit read -> explicit read for current CAS/IDs -> exactly one requested method -> explicit read for saved proof. Null selections skip their execute/interpret workers but still consume their declared decision; no substitute fills a slot. Normal paths have no retries or recomputations. Reports and scoring use saved JSON only, without API reopens or extra v2 checker calls.

“There are at most 384 normal capsule workers: 64 combined initial workers plus at most 320 later-stage workers. At most one additional globally terminal reconciliation worker may run after the first uncertain response. It may reopen/construct the existing capsule object and explicitly read once, with no create, mutation, replay, reset or continuation. It must then lead to structured terminal stop. If no readable authoritative capsule exists, do not recreate it. This is a whole-run allowance, not one per case.

“The whole-run API bounds are at most 1,986 capsule-validation entries, 1,986 cohort-proof reconstructions and 2,500 decision-proof reconstructions, for 4,486 independent D reconstructions in total. Count every actual producing/checking invocation, including failed work, inside whole-run CPU, wall, memory and output accounting. Keep scheduled/reserved slots separate from actual starts/completions. If an interrupted actual count cannot be established, report it as unknown and the result invalid while retaining verified counts. Reject extra dispatches before they start. No additional report/finalization read or checker pass is implicit.”

## Derived operation bounds

For each successful allowed-state validation, total D checker reconstructions are 1 plus its retained decision count. Early failures can do less; budget ceilings are not measurements of actual work.

| Worker | Validation entries | Cohort proofs | Decision proofs | D reconstructions |
|---|---:|---:|---:|---:|
| Combined create/read/reference/select/read | 6 | 6 | 2 | 8 |
| Stage-one execute | 5 | 5 | 5 | 10 |
| Stage-one interpret | 5 | 5 | 5 | 10 |
| Stage-two select | 5 | 5 | 7 | 12 |
| Stage-two execute | 5 | 5 | 10 | 15 |
| Stage-two interpret | 5 | 5 | 10 | 15 |
| Per-capsule maximum | 31 | 31 | 39 | 70 |
| 64-capsule normal maximum | 1,984 | 1,984 | 2,496 | 4,480 |
| One global terminal constructor/read | 2 | 2 | 4 | 6 |
| Whole-run maximum | 1,986 | 1,986 | 2,500 | 4,486 |

In the combined worker, create contributes two zero-decision validations, its explicit read a third, and select contributes one zero-decision pre-read plus a one-decision write validation; the final read validates one decision. Thus 6 validations yield 8 reconstructions. Combining removes two redundant zero-decision reads per capsule compared with version 1; decision-proof work remains unchanged.

The separate worker schedule had 448 normal capsule workers. Under the resource reviewer's conservative assumption of a one-second hard CPU allotment plus one-second granularity allowance per child, 448 workers consume up to 896 seconds before other workers/controller work. The combined schedule reduces the capsule-worker contribution to at most 768 seconds normally, or 770 including the single terminal reconciliation. **This alone is not a proof of the full 900-second CPU envelope:** neutral/probe/scoring/setup/reporting children and supervisor work must still fit the remaining global envelope, with every child and reserve counted once. The independent execution/resource reviewer owns that complete composition. No budget is increased here.

## Identity, termination and adoption conditions

- Seal full canonical D frames, unique chronological order, observation/receipt IDs and bodies, projected movement rows and the 32-unique-transition boundary. Require exact source descriptor and frozen generator/code/runtime/configuration identity. Same model output from different D/code is not sufficient.
- Compare complete cohort bytes and digest, including model order/bodies, raw discovery references, derivation branches, coverage statuses and code version. No majority vote, normalization of a differing actual source, replacement reference, cohort revision or favourable case substitution is allowed.
- Keep distinct native authority identities/path/inode validation intact. Within an anchor, both frozen logical input copies and both pre-action first T1 results must match semantically. Across different anchors, U/current world/context may legitimately differ; D and the layout cohort do not.
- Any cohort or source mismatch, including one discovered at a later anchor after earlier actions, invalidates and terminally stops the whole run. Do not retain a selectively successful prefix as the scientific result.
- The unchanged E1 mask is applied only at stage two after both first owned outcomes and T3 are complete. Current common observations can still imply information indirectly; the claim remains removal of the explicit updater channel, not total forgetting.
- Existing limits remain unchanged: 512 simulator invocations, 128 policy decisions, two decisions/two actions/2 MiB per capsule, 192 MiB output with terminal reserve, 512 MiB concurrent process-tree RSS, 15 CPU minutes and 25 wall minutes. Extra deterministic checking is charged inside them. Failure to fit is an honest terminal result, not permission to expand a running profile.
- All native adapter, choreography, controller, resource-plan and amendment descriptions must adopt this **same** combined schedule. Remove the superseded separate-create ordering and its 448/2,114/4,614 caps from active contracts while preserving version 1 as a historical document. The controller author and independent bounds reviewer both confirmed the combined 31/70-per-capsule derivation; their implementation must still be reviewed.
- The native API adapter remains unimplemented/unapproved in the reviewed context. Before any scientific stream, freeze and independently verify the actual call sequence, identity/reference handshake, exact count instrumentation, one-global-terminal-reconciliation path and complete resource composition. This memo's arithmetic is source-derived prospective analysis, not evidence that a real dispatch has run correctly.

## Disposition

The combined schedule is a justified minimal prospective amendment, with both scientific ordering and computation changes made explicit. It avoids an unnecessary API alteration and does not change the experimental evidence intervention. Preserve the original protocol and memo version 1; adopt and hash a new protocol version with this memo only through the separate pre-execution review process. Scientific execution remains unapproved.
