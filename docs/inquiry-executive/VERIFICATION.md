# Inquiry executive verification record

Date: 2026-10-07. Local copied implementation; not a remote-head/activation report.

## Source basis and boundary

- Implementation copy: reviewed draft PR217 `7d96cfa96901fd3f9d9c1893ff6fa0444c1847d1`, on PR213 `b3da508f6ebadc778cdb3cca5b9903997685d023`.
- The supplied production Core/agenda source matches current main `6aac9b8b7d1a785ce78d5045db5ade922ed2b6b7`; this report does not establish remote provenance or claim a new published commit.
- Every base-owned file was compared against the untouched implementation source copy: zero changes. `src/`, existing experiments, normal scripts, workflows, production defaults and schemas remain exact. New files are confined to the research package, its tests, and these design documents.
- Frozen design SHA-256: `5f2b16d905173ea0ed14d9780c5dad3174fffd3dce6713acd950b9833338e5e6`.
- Frozen acceptance SHA-256: `75646a100a5fdc29f28a5bf3635c97831464a77b9884620760caa5b4cff73633`.
- New package/test file-list manifest SHA-256: `77c91ff14e8a852c3f3fef850e65724d17cb373f761eaa521e604742a51a7b75`. The coordinating review retains the complete manifest; each created capsule additionally embeds the complete actual loaded-code manifest and copied-input hashes.

## Passed local checks

Command:

`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -p 'test_inquiry_executive_*.py' -v`

The final independent focused run passed 21 top-level tests in 105.645 seconds:
15 process/crash/concurrency tests, 4 exact-source-loading tests, and 2 isolated
suite wrappers. The wrappers passed 17 bridge and 24 contract tests. This is
60 substantive cases, or 62 reported test cases including the wrappers. Test
subcases add parameter coverage; they are not independent scientific trials.
The source/test tree stayed unchanged throughout that run.

The final 24-case contract suite also passed independently in 22.648 seconds.
Earlier development/duplicate runs are not added to the final denominator.
Final loaded-source manifest:
`3e7325460b69f9cef733b6d48fd94fab6c633fe263207df519c6e3568cb5c69c`.

Coverage includes:

- Real unchanged Core/agenda ownership, exact result/event/routing consistency,
  no caller winner override, no runner-up substitution, no-decision and unmapped
  nulls, and complete pre/post snapshot retention.
- Exactly one ordinary cycle, all provider/lab/copy-public paths disabled, no
  scratch-store replay, unchanged normal resumption correction, and explicitly
  disclosed Planning Lab deferral and repository-observation omission.
- Original-publication grounding across fresh processes and frames; distinct
  durable inquiries, decisions, attempts, outcomes and canonical belief lineage.
- Wrong owner/source/world/actor, stale revisions and beliefs, mutated prediction
  or command, frame-chain gaps, duplicate IDs/keys, nonfinite JSON, unsupported
  fields/schema, and outcome transplantation reject without writing authority.
- Atomic full outcome persistence, blocked commands consuming one action, missing
  evidence staying unevaluable, contradictory/agreeing hypotheses, and no
  duplicate or changed-rule interpretation.
- Exact serialized capacity boundaries, null decision accounting, exhausted
  decision/action stopping, admission oversize, reserved completion space,
  maximal serialized completion envelopes, and oversize outcome rejection with
  unchanged world. T2/T3 recovery remains possible after decision exhaustion.
- Symlink/hardlink/path relocation rejection, original input immutability,
  stable process lock across replacement, concurrent selection CAS, concurrent
  one-attempt execution and concurrent interpretation.
- Process termination before/after T1 temporary write/fsync/replacement; after
  pure transition computation before T2; before/after T2 replacement and lost
  response; before/after T3 replacement; and a waiting process surviving a killed
  lock holder. Old/new capsule states remain atomic, full results survive restart,
  and an already committed action is never transitioned again.
- Corrupt/truncated/missing authoritative files are rejected; stray temporary
  files are not recovered. Creation retry safely reuses an orphan stable lock.
  Failed derived export cannot cause replay.
- Warm dependency imports reject; post-import source mutation rejects; stale
  dependency bytecode is bypassed by pinned-source compilation; a valid stale
  bootstrap cache with the same source size/timestamp is rejected.

The tested durability boundary is the supported POSIX filesystem on this
execution environment. These are process-interruption and fsync-path checks,
not universal machine-power-loss guarantees.

## Small named controls, kept separate

These are deliberately authored valid synthetic states and tiny deterministic
source prefixes. Their fixture provenance discloses the closed legacy templates,
prior cycle and competitor-selection counters. Prefix-building actions are setup,
not ordinary ownership successes.

1. Retained-identity positive: 3 real ordinary selections, 3 distinct prepared
   attempts, 3 consumed actions, and 3 canonical interpretations, retaining the
   same original inquiry across fresh processes. At least one action is blocked
   and still consumed. This is wiring evidence only.
2. Two actual original publications with feature occlusion: 3 real ordinary
   selections, 1 consumed action. A's north move succeeds but hides its selected
   entity feature, so its interpretation is unevaluable. B is then selected but
   returns a generic experiment and safely defers. A's later return defers because
   the original feature is still publicly unavailable.
3. Real A→B→A interruption without actuation: B's generic returned experiment
   remains a null; A's old prepared authority is cancelled and its later return
   can receive fresh authority while the world is unchanged.
4. Injected routing state-machine control: prepared A→prepared B→fresh prepared A
   validates cancellation and single-capability machinery, with zero consumed
   actions. B's routing in this control is explicitly a test double. It does not
   establish real ordinary two-owner authority.
5. Unmapped winner and fewer-than-two-eligible nulls each commit one real ordinary
   decision/cycle and zero actions; neither executes an available runner-up.

Observed test assertions found zero accepted unauthorized ownership changes,
zero repeated durable action consumption, and zero duplicate belief credit.
Identical replay attempts return retained outcomes; conflicting/stale attempts
reject unchanged. A pure transition interrupted before commit may be recomputed,
but only one world revision and action consumption can become durable.

## Independent review changes

Review found three concrete implementation defects, fixed before final verification:

- Hashing current disk bytes did not establish which dependency code was already
  loaded. The design now refuses warm dependencies, pins before load, compiles
  those captured sources directly, and rejects a cached package bootstrap.
- Merely checking that a current-belief ID existed permitted a rollback to an
  older retained belief. The current belief must now be the latest canonical
  belief for that inquiry; ownership, predecessor chains and attempt-time belief
  references are checked as well.

- Python equality allowed a JSON boolean to impersonate an integral revision.
  Integral metadata now rejects booleans and equal-valued floats explicitly,
  including retained count/cycle/version metadata, attempts, receipts and
  filesystem identities. Canonical comparisons preserve JSON value types.

The current Ora snapshot is also anchored exactly to the initial copied source
or latest persisted real Core post-state, with only the recorder substituted
after a completed world action. This closes unprepared-state provenance drift.

Additional review hardened pinned directory reads/writes, safe creation retry,
post-replacement uncertainty handling, both recorder copies in the reserve bound,
and stopping new admissions/selections at either immutable budget limit.

## Full repository and baseline-owned preservation

Independent verification confirms all 134 implementation-base-owned files
unchanged, strict preservation **30/30**, and a baseline-owned comparator result
of **no regressions**.

The coordinator's final current-main overlay passed **471 top-level tests in
117.664 seconds**, plus **17 nested bridge and 24 nested contract cases**, on
the exact final package/test freeze identified above. Current-main-owned strict
preservation passed **30/30**, with **zero comparative regressions**. Earlier
interrupted/development/duplicate runs are historical verification only and are
not added to these counts.

Commands used by the unchanged workflow and final verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -v`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python scripts/preservation_eval.py --strict --output <current-eval.json>`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<base>/src python <base>/scripts/preservation_eval.py --output <base-eval.json>`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<candidate>/src python <base>/scripts/preservation_eval.py --output <candidate-eval.json>`
- `python <base>/scripts/compare_eval.py <base-eval.json> <candidate-eval.json>`

The placeholders identify the verified independent base/candidate copies and
separate output artifacts. Exact published-head CI remains a coordinator-owned
gate; a local green overlay does not establish remote CI or activation.

## Failed, unrun, and unestablished gates

- Final focused run: no failing tests. Earlier development runs intentionally
  exposed stale source/cache guards while files changed; they are not final passes.
- Real-selector two-owner A→B→A action authority: not established. B's actual
  generic-experiment routing is preserved as a null, not patched into a success.
- Preserved natural input smoke: never run. No preserved historical state or
  historical study prefix, natural seed sweep, PR218 rerun, or PR219 held-out run
  was performed. Required unchanged full-suite tests do include two legacy
  600-step unit fixtures built from `initial_state()` (1,200 setup transitions
  per complete run); these are legacy regression setup, not a preserved-history
  or natural inquiry study.
  Natural selection/action counts are therefore unrun, not a reported zero result.
- Sustainable long-history storage/compaction, hypothesis-set extension and
  meaning-migration/linked successors: not implemented or established here.
- Source authentication, hostile-writer defense, whole-capsule rollback defense,
  and external-world exactly-once effects: outside this local simulator proof.
- Exact published-head CI, remote merge and deployment: not performed by this
  implementation task; the coordinating task owns them. The current-main
  integration overlay was tested locally as reported above.

`learning_evidence: not_established`

`causal_resumption: not_established`

`live_activation: false`
