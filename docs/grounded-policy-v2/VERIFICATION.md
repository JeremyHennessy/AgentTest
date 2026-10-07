# V2 verification and limits

2026-10-07. Verification of the separate default-off grounded-investigation
API/policy, not a scientific-learning result or activation report.

## Exact source basis

The supplied baseline is draft #222 head
`076eb5c8ec8939a26060d657c5feacfa57c9d84e`. All 150 inherited files are unchanged.
The four approved design documents and the final design review are copied
byte-for-byte under `approved-design-2026-10-07/`; their original hashes remain
those printed in the preserved review. V1 source and its source manifest remain
unchanged, and an existing zero-transition v1 capsule reopens unchanged with the
new separate package present.

The final v2 repository closure contains 46 Python files. Its canonical manifest
digest is `79596c1a670cfb9cd201e0e163d43924ab98eb00473688f75669f7b8d64a6078`.
It includes the entire v2 package, all production Python modules conservatively,
and seven unchanged adapter dependencies. The policy itself imports no world or
authority code. Captured standard-library `fractions`, `decimal` and `numbers`
sources, trusted compiled Decimal identity, Python identity and libmpdec version
are separately pinned in each capsule's numerical runtime manifest.

The local runtime is CPython 3.12.14 with libmpdec 4.0.0. Other interpreter and
standard-library facilities are trusted installed runtime, not a hostile-Python
sandbox. Exact local and remote source provenance are distinct; publication and
remote CI are coordinating-task responsibilities.

## Final gates

The final aggregate passed **481 top-level tests in 218.369 seconds**, including
four subprocess wrappers. Their nested suites passed **36 v2 policy, 21 v2
transaction, 17 legacy bridge and 24 legacy contract cases**. Thus there are 98
nested cases; excluding the four wrappers avoids double counting (575 substantive
cases overall). The v2 addition contributes 88 substantive cases: 36 policy,
21 transaction, 19 source-loading and 12 process methods. Process methods contain
34 separately bounded fixtures; parameterized subcases are not scientific trials.

All 116 Python files in the final source/test freeze remained unchanged throughout
the passing aggregate. No failing or skipped final gate was reported. The
aggregate command was run once on that final freeze:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B -m unittest discover -s tests -v`

Already completed on final runtime bytes:

- 36 pure-policy cases, zero world transitions.
- 19 source/numerical-loading cases, zero world transitions.
- 12 process/crash/CAS test methods covering 34 separately bounded fixtures;
  68 setup transitions, 34 owned transition invocations, 29 durable outcomes,
  maximum four calls per fixture.
- The unchanged baseline-owned preservation suite passes 30/30 against both
  baseline and candidate source. Its unchanged comparator reports no regressions.

The 21 transaction cases additionally cover full menu/derivation checks, current
state and belief anchors, identical first-arm behavior, the actual materialized
stage-two mask, exact byte boundaries, full 65,536-byte receipts, over-bound
outcome rejection, protected completion, replay, cancellation and truthful nulls.
Their final aggregate passed on the hardened numerical runtime; earlier
pre-numerics-hardening runs are not substituted for that gate.

## Independent implementation review

The independent reviewer retained these separate checks:

- 48 pure numerical/model oracle fixtures, with no simulator calls.
- One six-call hand-authored paired API control: two common D setup moves and
  four owned actions, all T1/T2/T3 operations in fresh interpreters. The first
  selections/outcomes/interpretations agree, and only the retained stage-two
  view adds the first event. This is an invariant control, not one of the
  separately gated scientific 32 paired cases.
- 17 re-sealed saved-authority negative cases, zero simulator calls.
- Frozen v1 reopening, unique-event boundary at the 65-frame cap, source closure,
  captured numerical compilation, unsupported warm-import refusal and old-source
  capsule rejection, all without transitions.

The six-call control and saved-authority attacks preceded the final numerical
closure fix. Only `__init__.py` and `contracts.py` changed afterward; policy,
view, transaction and storage logic stayed byte-identical. The reviewer tested
the affected numerical/source boundary separately without rerunning the pair.
The final aggregate tests exercise the complete final runtime.

## Findings fixed before freeze

1. Raw delivery count initially bounded duplicate frames before deduplication.
   The unique chronological 65-frame bound and unique D/U boundary now apply
   after exact-body deduplication, with a separate raw-byte bound.
2. An audit receipt could initially be changed to an unjustified capacity null.
   Validation now reconstructs the exact selected-state serialization and
   immutable action allowance, proving the unique capacity result.
3. Current numerical source/loader inspection did not prove which bytes a warm
   Fraction module had executed. The final bootstrap rejects warm numerical
   imports, captures trusted numeric sources before use, compiles those exact
   bytes, ignores stale bytecode/PYTHONPATH shadows, and requires the trusted
   compiled Decimal runtime. The independent stale-loaded-source reproduction
   now fails closed.

Earlier development failures in numerical runtime inspection are preserved in
local logs. They are not final passing tests. An interrupted process-test run
completed only its first method; the following fixture had durably committed T2
before interruption. Its six actual calls and two durable outcomes are counted
separately using append-only invocation logs plus the authoritative capsule,
not an outdated derived marker.

## Counts are software checks, not scientific samples

The final aggregate v2 controls made **158 actual simulator calls**: 113 tiny
setup transitions and 45 owned transition invocations, producing 39 durable
outcomes. Six extra owned invocations were uncommitted failures/recomputations.
The 57 final v2 fixtures comprise 23 transaction and 34 process fixtures; pure
policy/source controls add no transitions.

Across all logged implementation development, focused verification, the final
aggregate, the separately retained partial process run, and the independent
six-call paired invariant, there were **408 new synthetic simulator calls**:
304 setup plus 104 owned invocations, producing 92 durable outcomes. This is
software-test accounting, not permission to consume the later scientific budget.
No fixture exceeded the 16-call allowance.

Nested suite cases and top-level subprocess wrappers are listed separately in
the final aggregate summary. Repeated development/focused runs are not added to
the final test denominator. New synthetic transition counts are separately
reconciled in the local accounting report, including failed/partial tests and
uncommitted crash recomputations.

The unchanged full baseline suite includes two legacy 600-step fixtures built
from `initial_state()` (1,200 setup transitions per complete aggregate). They are
baseline regression setup, not historical-input replay, a new natural run or a
v2 scientific study. Other unchanged baseline tests retain their own ordinary
unit-test behavior; no aggregate scientific denominator is inferred from them.

## Unrun and unestablished

- No scientific 64-step streams, 32 paired cases, evaluator probes, historical
  input, #218/#219 rerun, scorer process or scientific entrypoint was run.
- Scientific runner, independent scorer, whole-study resource supervisor and
  pre-execution freeze remain a separate future reviewed task. The proposed
  512-call study ceiling is not a development-test budget or permission to run.
- No Core cycles or providers are invoked by v2. Unchanged baseline regression
  tests naturally exercise their existing Core paths.
- Publication, merging, deployment and live activation were not performed here.
- Hypothesis/representation evolution, long-term learning, calibrated models,
  cross-context transfer, comparative realized action utility, general noise
  robustness and useful natural Ora learning remain unestablished.
- Local POSIX interruption/fsync tests do not prove universal power-loss
  durability, hostile writer resistance, whole-capsule rollback prevention or
  external-world exactly-once effects.

`selection_backend: grounded_policy_v2`

`learning_evidence: not_established`

`scientific_run: unrun`

`live_activation: false`
