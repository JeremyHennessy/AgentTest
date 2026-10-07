# First-slice acceptance and review checklist

Status: planned tests, none run by this design task. No expensive study rerun required.

## A. Exact legacy boundary

- Hash `src/`, normal CLI, production schema/defaults, and legacy lab paths against the pinned implementation base. Prefer no changes to any of them. New research package must not be imported by production.
- Run all repository unit tests and the base-owned strict preservation/comparison commands from `.github/workflows/verify.yml` on the eventual implementation commit.
- Compare representative normal cycles with planning off/on and action lab off/on, fixed inputs/time where supported. Check old result/state/journal behavior, allowing only already nondeterministic timestamps.
- Show the copied executive's explicit Planning Lab deferral. Spy on both old lab step functions and the new transition function: zero lab transitions; zero or one owned new transition. A missing deferral field fails. Verify the narrowed envelope makes exactly one ordinary selection, cannot enter the recursive scratch-store branch, preserves the normal corrective handling of provisional resumption counts, and discloses omitted repository observation. Verify no caller can expand that envelope.

## B. Ownership and identity

- Unselected, suspended, archived, unmapped, ambiguous, unsupported, and no-decision cases produce no capability or world transition. An available runner-up never substitutes for the winner.
- Selection record must match the actual ordinary result, latest decision, cycle, foreground thread, question, owned experiment/routing, stable inquiry binding, and source/code manifest. Preserve full pre-cycle inputs and disclose bounded candidate summaries. Reject a fabricated decision or `selected=True` caller assertion.
- Exercise current agenda's fewer-than-two-eligible null. Preserve real natural competition, including the known default/native nonselection cases.
- Stable inquiry survives several public frames and a process restart without requiring current-publication candidate-ID equivalence. Each new action has a distinct attempt, decision, frame binding, and prediction. Question-text collision and legacy experiment deduplication cannot merge ownership.
- Every committed outcome traces uniquely to one pre-action prediction and selected owner. No learning/progress metric is incremented merely for event count or belief version.

## C. Freshness, budget, concurrency, confinement

For each field below, issue on an independent copied fixture, mutate it, and assert all authoritative capsule bytes, counters, inquiry/decision/recorder/belief lineage, world, and budget are unchanged by the rejected request, including fresh-process retry:

- Inquiry/hypothesis/belief version; ordinary decision/question/thread; command/prediction; current public observation/context; source/world/actor identity; recorder chain; code manifest; budget; capsule revision/path/run identity.

Also test duplicate IDs, malformed/oversized/unknown JSON fields, duplicate keys, nonfinite values, missing source frames, nonadjacent evidence, feature disappearance, and outcome transplantation from a different attempt.

- Two simultaneous executors using one prepared attempt yield exactly one committed transition; second gets stored result or a conflict. Competing selections cannot leave two pending capabilities. Locks are process-level, not merely Python object locks.
- Enforce immutable profile limits: synthetic defaults 2 MiB / 8 decisions / 4 actions, hard maxima 16 MiB / 16 decisions / 8 actions; separately declared one-input smoke at most 256 MiB / 1 decision / 1 action. Null decisions count. Exhausted budget and capacity are durable stopping conditions; reopening never resets them. Blocked command consumes exactly one action.
- Test exact byte-limit boundaries (canonical serialized bytes including seal/newline), one-byte-over rejection, admission oversize, decision/action exhaustion, and T1 outcome-reserve shortfall. Every failed precommit leaves all bytes/counters unchanged. Prove the schema-bounded 1 MiB completion reserve under worst-case allowed receipt/frame/belief sizes; no transition preview may inform selection. T2/T3 fit without trimming evidence, or fail without changing the copied world. Recovery of already committed work is allowed after decision exhaustion. Attempt admission/null-selection growth between T1/T2/T3 and verify outstanding completion capacity cannot be consumed; release it only on prepared cancellation or canonical T3.
- Default-disabled call, default/live path, path alias, symlink/hardlink, relocation, missing reopen file, and unsupported store version fail closed. Assert protected source stores and production files are byte-identical.
- Policy spies receive only public views; private fields and future outcomes never enter selection/prediction. No real shell/network/tool execution can be reached through a command string.

## D. Crash/restart matrix

Inject process interruption, not just exceptions, at these boundaries:

1. Before/after T1 temporary write and atomic replacement.
2. After T1 but before execution.
3. After pure transition computation but before T2 replacement.
4. After T2 replacement before caller response or public-evidence ingestion.
5. Before/after T3 replacement.
6. While a second process contends for the lock.

Reopen in a fresh process; validate that state is wholly old or wholly new, pending/consumed status agrees with world revision and budget, full receipt/outcome can be recovered after T2, and interpretation occurs at most once. Reject corrupt/truncated authoritative state; do not silently create initial state or treat a stray temporary file as committed. An export/journal failure cannot cause action replay. State clearly that machine/filesystem durability guarantees are tested only on the supported filesystem, not universally.

## E. Interruption and outcome semantics

- Prepared A is interrupted by a new normal decision selecting B: A is cancelled, B owns the only current authority. Later ordinary return to A creates new authority; old A is unusable.
- Restart with unchanged prepared A may complete A once; restart itself never selects A.
- Committed A pending interpretation is recovered without a world call. A missing interpretation rule exposes a blocker and prevents new actuation.
- Successful, blocked, missing-feature, contradictory, and nondiscriminating outcomes each persist exact public evidence. Missing evidence is unevaluable, not support/refutation. Pre-action predictions remain byte-identical after outcome arrival.
- Repeated interpretation returns the existing belief version; changing the interpretation-rule version cannot create another update from the same outcome. Full completed-outcome evidence remains available until the capsule stops at capacity. Agreement of two hypotheses does not manufacture a winner. Delayed evidence from another action cannot resolve this attempt.

## F. Evidence labels and honest nulls

Use tiny deterministic copied fixtures, not the historical 600-step prefix or fresh seed sweeps, for positive ownership/crash controls. Include at least one deliberately constructed but valid synthetic state that passes through the real unmodified Core/agenda selection call and naturally wins within that synthetic input. Do not mock/inject selector output. Label this `synthetic_control` with exact fixture provenance; it proves state-machine wiring only, not spontaneous inquiry formation or natural selection in retained production states. Runtime entrypoints cannot accept a selector-override flag or caller-selected owner.

Separately exercise the unmodified ordinary bridge on exactly one declared preserved natural competition input for one decision/cycle, under the explicit `preserved_input_smoke` cap and input hash. Record actual selected question, mapped inquiry, action count, and null reasons. A synthetic selection is never included in the natural denominator. Do not force a positive result, tune ranking, change candidate pools, reconstruct old prefixes, extend the smoke horizon, or rerun PR218/PR219 to make this slice pass. Report sustainable long-horizon persistence as not established.

Required report fields:

- exact base/head/source manifest and commands executed;
- passed, failed, and never-run checks separately;
- synthetic selection/action counts separate from ordinary counts;
- ownership failures, replay attempts, crash recoveries, deferrals, unavailable features;
- legacy-planning deferral treatment and preserved live-file hashes;
- `learning_evidence: not_established`, `causal_resumption: not_established`, `live_activation: false`.

## Review gates before implementation/merge

1. Independent design review resolves ambiguous ownership, persistence, source, and disabled-path behavior.
2. Implementation stays within this transaction slice. Generation/policy changes receive a separate proposal and review.
3. All targeted tests plus repository preservation pass on the exact published head. Focused checks alone are insufficient.
4. Inspect diff for unexpected production/workflow/state/experiment-result changes.
5. No activation, learning milestone, autonomous selection success, or causal claim is inferred from a green test suite.
