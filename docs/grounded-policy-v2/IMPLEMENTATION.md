# Grounded investigation API v2

2026-10-07. Default-off copied-world research software. This is an API and
invariant-test implementation, not a scientific effectiveness result. The
approved design and its independent design review are preserved byte-for-byte
in `approved-design-2026-10-07/`.

## Narrow boundary

`experiments/grounded_policy_v2/` is physically separate from the unchanged
`experiments/inquiry_executive/` v1 namespace. No production module, old
experiment, script, workflow, old data, or frozen report is changed. All 150
files inherited from draft #222 head
`076eb5c8ec8939a26060d657c5feacfa57c9d84e` remain byte-identical.

This is `selection_backend=grounded_policy_v2`. It does not run Core, claim a
Core-selected experiment, substitute a runner-up, call a provider, or grant live
world authority. There is no scientific runner, scorer process, whole-study
supervisor, neutral-stream generator or study entrypoint in this package. The
pure half-Brier arithmetic helper accepts a supplied class; it cannot obtain an
outcome or execute a study.

## Public API and lifecycle

Import the v2 package before Ora/Challenge or numerical modules in a fresh
`python -B` interpreter. Warm `fractions`, `decimal`, `numbers`, `_decimal` and
`_pydecimal` imports are rejected. Trusted installed `fractions.py`, `decimal.py`
and `numbers.py` are captured before use and compiled directly from those bytes;
PYTHONPATH shadows and stale bytecode are not used. Compiled Decimal is required,
with its standard-library/builtin origin, binary identity when applicable,
libmpdec version and interpreter identity pinned. Pure-Python fallback is not
supported. Other installed interpreter/standard-library facilities remain the
trusted runtime; this is not a general verifier of hostile warm Python state. Explicitly create a new capsule with `enabled=True`, copied source
paths for `ora`, `world`, `observations`, and `discovery_count`. An observation
source is a list of `{observation, receipt}` frames starting at cycle zero. The
world must match the final sensor and the entire public receipt history. Ora is
an immutable copied object, never a policy input or an implicit live StateStore.

Creation pins backend, exact source descriptors and copied file identities,
full repository-code and numeric-runtime manifests, scientific configuration,
unique-event discovery boundary, evidence mode, source actor/world identity,
filesystem directory/lock identity and budget. The only profile is
`synthetic_two_decision_v2`: at most two decisions, two owned actions and 2 MiB
canonical capsule bytes. Smaller immutable bounds are allowed. There is no
migration, fork/reset/reseal API, profile expansion, caller-supplied policy or
legacy backend adapter.

- `GroundedExecutive.create(...)`: construct the D cohort once, validate full
  copied inputs, and create a new authoritative file through the stable lock.
- `select_next(expected_revision)`: T1. Materialize the allowlisted view, call the
  producing backend exactly once, prove its complete result independently,
  commit all four movement forecast-or-coverage rows, immutable compiled cases,
  the selected owner/experiment or truthful null, and one prepared attempt.
- `execute(attempt_id, expected_revision)`: T2. Check latest selected ownership,
  original command and current public membership, apply one pure copied-world
  transition, and atomically save the world and complete actual public outcome.
- `interpret(outcome_id, expected_revision)`: T3. Canonical immutable-case
  support/contradiction only, anchored to the durable outcome and latest prior
  interpretation. This is not a global model truth value.
- `cancel(attempt_id, expected_revision)`: cancel only the latest prepared
  authority. Cancellation is terminal for this two-decision capsule; it cannot
  stand in for completing the first owned lifecycle.
- `read()`: reopen and independently validate sources, derivations, policy proofs,
  exact capacity decisions, state anchors, ownership and all retained history.

The second selection requires the first owned T3 or a truthful first null.
Nulls consume decisions, not actions. Action/byte capacity nulls preserve the
backend's actual suggested movement in the audit body but issue no owner or
attempt. The validator reconstructs the exact would-be selected serialization
and budget failure, so an unjustified capacity null is not an alternative
selection authority.

All mutating methods use strict integral CAS. Retrying a consumed attempt or
interpreted outcome with the current revision returns its saved result without
an action or new belief. A stale revision fails; after an uncertain response,
reread the authoritative capsule rather than blindly replaying. An uncommitted
pure transition interrupted before replacement may be recomputed, but only one
world/outcome commit becomes durable. Such invocations need separate accounting
in any future whole-study supervisor.

## Policy and evidence boundary

The pure policy imports only pure JSON/hash primitives and standard numerical
libraries. It receives no world, action function, callback, source path,
layout ID, previous decision, cached posterior or authority object. Source IDs
and hashes establish audit equality, never scores or predicate ranks.

D infers zero and one nonzero observed movement delta. Missing diversity,
multiple nonzero deltas or more than 128 eligible conditionals produces an
explicit unavailable reason. Retain two observed constants and at most five
conditionals, ordered by construction loss, syntax size and chronological
structural order. A disclosed authored unresolved model N has no T3 categorical
claim. The generator never sees U or E1. The verifier reconstructs the full
cohort independently without calling the producing generator.

Availability is fixed from cohort/current public context before evidence. One
available concrete rule permits a forecast; two different concrete predictions
permit an inquiry. Unavailable concrete models have no prior/weight contribution.
Only unique post-D events with exactly matching public context and movement
update the uniform available-model-plus-N prior. Rational probabilities are
reduced numerator/positive-denominator decimal-string pairs with a 256-digit
bound. Entropy uses 50-digit Decimal logarithms, half-even 18-place serialization,
a strict greater-than-0.01-bit threshold, and a 1e-12-bit tie tolerance in
north/east/south/west order. Shared arithmetic is not a second backend invocation.

Full raw source frames and actual owned outcomes remain in both authoritative
capsules. Evidence mode is creation-only. Stage one is identical. At stage two,
`retain_first` includes the first actual owned transition; `withhold_first`
removes its explicit updater row. The trusted mask receipt binds included and
excluded hashes, current projection and prior-state anchor outside the policy
view. The latter contains only the common cohort, current public context,
common U plus permitted E1, and outcome-free matched lifecycle fields. No E1
owner, pre-frame, action, receipt ID, prior forecast/belief, recorder counts or
path leaks through another policy input. Current context can still indirectly
reveal information; total ignorance is not claimed.

Duplicate raw delivery is deduplicated by public observation identity only after
exact-body checking. The 65-frame cap and discovery boundary apply to unique
chronological frames, with a separate 2 MiB raw delivery bound. Unknown actual
source substitution still rejects. Opaque-ID alpha-renaming is a semantic pure
policy control, not permission to rewrite the authority source identity.

## Storage and exact completion space

The v2 capsule uses a stable sibling POSIX process lock, no-follow path traversal,
unaliased regular files, original copied-source inode/hash checks, directory
identity checks, fsynced temporary replacement and directory fsync. Temporary
files are never recovery inputs. A post-replacement fsync failure is reported as
commit uncertainty. This is a local integrity/durability boundary, not hostile
OS protection, external-world exactly-once execution or whole-capsule rollback
protection.

A complete cohort and each decision are capped at 256 KiB. Each public observation
or receipt is capped at 65,536 canonical bytes. T1 reserves 524,288 bytes.
T2's new full outcome retains before observation, after observation and receipt;
the same receipt also enters the copied world's history. Four 65,536-byte records
plus 16,384 bytes for ownership/hash/event/status metadata bound growth at
278,528 bytes. The current fixed world changes only its bounded position and
cycle, not its private structure. T2 then retains a 65,536-byte interpretation
reserve. T3 adds at most seven verdicts, fixed-length hashes and one event, bounded
at 16,384 bytes. Both inequalities have strict margin. Every write also measures
exact canonical serialization (including seal and newline), checks its remaining
reserve against the immutable profile, and checks actual T2/T3 growth.

Tests cover a receipt exactly at its 65,536-byte bound, an over-bound outcome
rejected before persistence, exact selected-byte threshold versus one byte less,
and successful protected T2/T3 after reserving completion. These are v2 checks;
v1's older completion proof is not assumed equivalent.

## Limits and later gate

The fixed language cannot invent features, actions, multi-step mechanisms or new
representations. A later context produces a separate immutable case. No
hypothesis extension, long-term learning, cross-context transfer, comparative
realized action utility, efficient exploration or noise robustness is established.
The tiny blocked-movement fixture is deliberately authored for ownership/masking
controls; its posterior movement is not an effectiveness result.

Before the separately locked 32-pair study, its runner/scorer and whole-process
resource supervisor still need implementation, source freeze and independent
pre-execution review. This package does not enforce or consume the scientific
512-invocation allowance. No four-layout 64-step stream, held-out probe, historical
input, #218/#219 rerun or scientific pair was generated here. Normal unchanged
baseline regression tests are separate software gates, including their two
600-step `initial_state()` fixtures.
