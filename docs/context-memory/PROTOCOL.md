# Ora copied-only context representation study, version 1

Status: **design for review; not implemented or executed**. Date: 2026-10-07.
Companion settings: `settings.json`. Any conflict between these files blocks execution.

## Decision this study can support

Test whether replacing a research selector's global action-effect counts with
eligible exact-public-context counts improves its one-step falsification choices
on a fixed, previously uninspected context cohort. This is a representation/policy
experiment, not a repair to lost evidence, and not a readiness or activation test.

The negative result in draft PR #218, head
`3ec6e83b0716ab07046564217ad6a361e4de75dd`, remains frozen. Global associations
updated correctly; the observed five repeats at [2, 2] motivate this hypothesis
but cannot be counted as held-out successes. Native evidence reaches agenda references: default and production action-1
probes change priority from 0.35 to 0.50, while production action-8 probes change
it from 0.35 to 0.15 because completion removes an active experiment path.
Higher-priority candidates legitimately win in both cases.
Consequently agenda scores, priorities and ordinary native choice are outside
this experiment. No AgentCore cycles or historical organism snapshots are needed.

Runtime reference is exact PR #213,
`b3da508f6ebadc778cdb3cca5b9903997685d023`. Draft #217's guarded executor,
`7d96cfa96901fd3f9d9c1893ff6fa0444c1847d1`, is a separate lineage and gate.
Neither it nor #218 is modified or silently combined with this study.
The world transition function is used only for offline, disposable simulator
evaluation. The native capability executor is neither invoked nor bypassed;
no native authorization is requested, issued, or claimed by these probes.
Simulator internals remain in the evaluator and never enter policy inputs.

## Hypothesis and arms

H1: an eligible context-conditioned count projection reduces selecting actions
after repeated local non-refutation and increases actual one-step refutation
yield, without material loss of evaluability or calibration.

- Control: the exact frozen selector consumes the ordinary global association
  rows from the common public neutral prefix.
- Candidate: that same selector consumes a coherent conditional projection of
  those rows, defined below. Everything else is identical before selection.

There is one candidate, no parameter sweep and no score tuning. The unchanged
selector has policy `public-falsification-oriented-v1`, MIN_EFFECT_SAMPLES=2,
Laplace probability `(changed + 1)/(evaluable + 2)`, evidence weight
`evaluable/(evaluable + 2)`, and score
`falsification_probability * (0.25 + 0.75 * evidence_weight)`. Preserve its exact
rounding, both tie rules, and public command enumeration. In particular, one local
sample may cause a second uncertainty-driven attempt. A zero-retry requirement
would quietly conflict with the frozen policy and is not a success criterion.

## Public representation and exact intervention

Canonical JSON is UTF-8 with Unicode characters unescaped (`ensure_ascii=False`),
sorted object keys, compact separators, no NaN, no added whitespace. Define
C(observation) as a JSON object from validated public observations only:

- world_version;
- observed position, preserving coordinate order;
- lexically sorted inventory_ids;
- visible_entities sorted by id, each containing id, position, appearance and
  observable_state **if present**. Absence differs from an empty state string.

Exclude cycle, observation ID, receipt ID, clock, layout ID, run seed, objective,
last action and receipt outcome from C. Keep `action_label(command)` separate.
Do not infer object kinds, map topology, routes, rewards or unobserved state.

For every validated adjacent public transition, store pre-context C, action label,
the public before/after values, and the original blocked receipt. Increment
global and local counts for the intersection of the before/after feature sets,
using the existing `public_features` equality semantics. Features disappearing
from visibility are non-evaluable, not unchanged. Local keys are
`(C, feature, action_label)`; local feature totals sum all actions at C. Receipts
are evidence, never a reason to remove an action. In particular, blocked does
not imply failure to refute a `changes_next_observation` claim.

At a query, begin with an exact copy of the control's global row list. Preserve
its row population, order, IDs, feature/action labels and relation values. For a
row, derive local present counts P and local absent counts A = local feature
totals minus P. Replace that entire row's measured statistics **only if**
P.evaluable >= 1 and A.evaluable >= 1. Otherwise leave it byte-for-byte global.
Replacement statistics are coherent local values for action_present,
action_absent, evaluable, effect_difference and status, calculated with the
original exporter formulas/rounding. Do not add a row suppressed by the original
exporter's action-absent requirement, fabricate counts, blend local and global
sample sizes, or label mixed counts as a measured association.

Record projection provenance in a separate study sidecar, not in the recorder or
native evidence registry. A conditional row is explicitly a query projection,
not a changed source record. The selector reads action_present; preserving the
other statistics coherently makes this projection auditable.

This backoff has an intentional discontinuity: zero eligible local support uses
global exposure; one eligible local observation can invoke local uncertainty.
It does not automatically explore every unseen context/action pair. Record this
behavior rather than smoothing it after seeing results.

A changed public context uses a different key. A formerly blocked action remains
in candidate_commands and can be retried; no direction-specific rule, blacklist,
time-to-live, decay, special west treatment or permanent exclusion is allowed.
If the same exact C returns, its retained local evidence returns too. Exact public
contexts can still alias hidden states; this study does not assume they are
sufficient Markov states.

## Development, legacy exclusion and held-out contexts

The unit of separation is a **pre-action public context group**, not a seed or
individual transition. The world has only four mirrored layouts; seeds above four
are not extra independent layouts.

Define G(C) for split assignment only: serialize C under all four independent
coordinate sign flips, applying the same flip to the observed position and every
visible entity position; take the lexically smallest canonical byte string.
Do not change IDs, appearance or inventory. Compute
SHA256(UTF8(`ora-context-holdout-v1|`) concatenated with G(C)). Its first byte
0–127 is development; 128–255 is potentially held-out. The policy always uses
original exact C, never G or a transformed action. Grouping mirrored contexts is
a conservative split rule, not a geometry hint supplied to either policy.

Build a legacy exclusion set L before implementation freeze:

1. Reconstruct the old four 600-transition neutral prefixes using exact #213
   initial_world, original choose_command and empty per-run attempt counters.
   Include G(C) for every observation from cycles 0 through 600.
2. Include G(C) from all 64 archived retained/ablated selector-input files in the
   frozen #218 audit package. Verify member hashes against its existing manifest;
   these include post-prefix study contexts.
3. Deduplicate and sort groups; save and hash the list. No outcome-based removal.

All groups in L are development-only, regardless of split hash. Missing or
unverifiable legacy inputs block the confirmatory run; do not silently exclude
only the famous west example. Replaying old neutral transitions solely to define
L is budgeted below and is not a new scientific trial.

Development uses those legacy inputs and 32 synthetic public-transition fixtures
whose pre-context groups either belong to L or hash to development. There is no
fresh development-world search or optimization run. Fixtures must exercise the
rules rather than prescribe beneficial held-out outcomes. If implementation
needs a new feature or policy choice, revise and review the protocol before any
held-out execution. Synthetic contexts that accidentally hash to held-out cannot
be used; change only an arbitrary synthetic ID before any fixture outcome is
assigned, record this construction, and never redraw a real evaluation context.

A confirmatory anchor must have G(C) outside L and hash to held-out. All
occurrences of a group in every layout/run share this assignment. This guarantees
disjoint pre-action query contexts, including mirrored equivalents. An after-state
appearing as a public observation is not by itself a training example of an
action taken in that context. The claim is held-out from design/fixture tuning,
not an unknown world-mechanics benchmark.

## Fixed corpus and evaluation schedule

After source/settings freeze, generate exactly four new neutral streams:

- layout seeds 1, 2, 3, 4, in that order;
- exploration seeds 1009, 2003, 3001, 4001 respectively;
- 1,024 actual neutral transitions per stream, including every unsuccessful or
  blocked action; no reset based on progress or outcomes;
- each stream begins from initial_world with independent empty evidence/attempt
  tables. Do not transfer knowledge between streams.

Neutral command selection is public, outcome-agnostic least-tried exploration.
Among candidate_commands, minimize `(attempt_count(C, command_key), tie_digest,
GENERIC_ACTION_ORDER index, command_key)`. tie_digest is the SHA-256 hex digest
of canonical JSON `["ora-context-neutral-v1", exploration_seed, C,
list(command_key)]`, where C is the context object, not a serialized string.
Increment the chosen command's attempt count once. The
seeded tie order generates a fixed new corpus; it is identical regardless of arm
and cannot inspect either arm's chosen command, receipts or scores. It supplies
no solution route or reward. It differs from the original explorer only for
corpus construction, not in either tested selector.

Potential query anchors are neutral cycles 128, 136, ..., 1016: exactly 112 per
stream, 448 slots total. At an anchor, before neutral transition t+1:

1. The public history contains only actual neutral transitions through t.
2. Obtain the single temporal feature/relation from the **unchanged global
   temporal publication/ranking** with information_gain. Do not condition or
   replace this objective in the candidate arm.
3. Include the anchor only if its group is held-out, an ordinary eligible temporal
   publication exists, and its selected feature is visible now. These checks use
   current observation/prefix only. No fallback objective or replacement slot.
4. Materialize and hash matched observation, query, common public-prefix identity,
   available command list, global counts and local counts before either decision.
   Select once per arm. Record the complete selector output and projection.
5. Clone the identical anchor world twice. Execute each arm's actual selected
   command exactly once at cycle t+1, including when commands agree. Compare
   actual public observations/receipts, never predicted alternative outcomes.
6. Discard both branches. Their outcomes enter the sealed evaluation log only.
   They never update neutral history, attempt counts, global/local memory,
   objective ranking or case selection. Continue the predetermined neutral stream.

The two arms therefore share observation, query, commands, prefix and one-action
budget before decision; only association representation differs. There is no
native experiment completion/resolution contrast or lifecycle confound.

## Permitted online evidence, and leakage prevention

Held-out means the algorithm is frozen before seeing these contexts' new outcomes.
At anchor t, both arms may consume neutral outcomes 1..t, including earlier
occurrences of the very same held-out context. This is prequential adaptation,
not a train/test leak: an outcome is available only after its actual neutral
transition. Exclude t+1 and every probe-branch result from both inputs. A cold
context with no eligible local rows must reproduce the global control exactly.

Generate and evaluate streams with the frozen runner without interactive outcome
inspection or parameter changes. Seal the full event log and final count file
before unblinding. An implementer may inspect mechanical progress and resource
usage but not intermediate effectiveness metrics. Case eligibility never depends
on completed probe outcomes. Repeat-opportunity and blocked-event strata are
computed retrospectively from earlier neutral evidence; they do not control
which probes run.

## Endpoints and finite-corpus acceptance rules

For each actual arm transition, y=1 if the queried feature is present before and
after and the transition refutes the shared relation; otherwise y=0. Missing
features remain in the denominator with a separate non-evaluable flag. A blocked
transition may have y=1 for a changes-next claim. Receipt success alone is not y.

Primary yield is the mean of y within each G group, then the equally weighted
mean across groups. Delta is candidate minus control on the same anchors. Also
report micro totals, paired wins/losses/ties, per-layout summaries and the actual
outcomes of every disagreement. These deterministic, correlated contexts do not
support iid trial p-values or a broad generalization claim.

Define the common-prefix set D at an anchor as available actions with at least
two earlier evaluable executions at the same exact C and feature, whose **last
two** outcomes did not refute the current relation. An arm repeats when its
selected action is in D. Primary repeat rate uses anchors with D nonempty; report
the extra strata with a prior blocked receipt and with the control's current
effect-seeking falsification probability >0.5. Call this “repeat selection after
two prior local non-refutations,” not autonomous persistence. Retain n=0, n=1,
n>=2 and eligible-local-versus-global-backoff diagnostics separately.

Coverage is sufficient only if all are true:

- at least 96 included paired anchors and 16 held-out G groups;
- each of four layouts has at least 16 anchors and four groups;
- at least 64 anchors have evaluable actual outcomes in both arms;
- at least 24 anchors have D nonempty, spanning eight groups and three layouts;
- at least 24 anchors use an eligible local projection for the queried feature
  and at least one **currently available** command, spanning eight groups and
  three layouts. Replaced rows for unavailable historical actions do not count.

Predeclared representation-benefit pass requires sufficient coverage and all:

1. Context-balanced actual refutation yield improves by at least 0.10 (10 points).
2. Context-balanced repeat rate on D-nonempty anchors falls by at least 0.20.
3. Candidate actual refutation micro-total is at least control's.
4. No layout's micro refutation yield falls by more than 0.05.
5. Overall non-evaluable rate increases by no more than 0.02, and no layout's
   non-evaluable rate increases by more than 0.05.
6. Paired-common-evaluable selected-action predictive Brier loss increases by no
   more than 0.02 overall. On the common set E of anchors evaluable in both arms,
   each arm's loss is `sum((p_arm - y_arm)^2 for anchor in E) / len(E)`, with p
   equal to that arm's frozen selector output falsification_probability. Compare
   candidate loss minus control loss. Each predicts its own chosen command; this
   is not pure calibration on identical actions. Also report arm-specific
   evaluability so this guard cannot conceal dropout.
7. Every mechanical/integrity gate below passes.

Use context-balanced repeat averages over the same D-nonempty group set, and
ordinary micro averages for explicitly micro guards. Round only displayed
metrics, not gate calculations. Thresholds are practical, preregistered corpus
decision limits, not estimates derived from the old 5/5 result.

Every metric records its denominator. A zero denominator is unavailable, never
zero or a pass. In particular, an empty layout cannot pass its regression guard,
and no paired-common-evaluable transitions means calibration is unavailable.
An unavailable required metric makes the final result inconclusive unless an
observable integrity failure or regression already requires invalid/adverse.

Classification order: integrity failure -> invalid; a breached regression guard
(3–6) -> adverse regardless of coverage; insufficient coverage -> inconclusive;
sufficient coverage but missing either improvement threshold -> no demonstrated
benefit (including null); otherwise -> finite-corpus representation benefit.
Report all counts even for negative results. No pass permits merge, live
installation, reward-policy changes, native milestone credit or activation.

## Mechanical gates and development fixtures

The 32 fixed fixtures comprise eight categories with four variants each:

1. canonicalization, ordering, field presence, coordinate transforms;
2. feature intersection, changed/same counts, disappeared features, receipt checks;
3. coherent global/local present-and-absent row export;
4. n=0 backoff identity, n=1 uncertainty, n=2 behavior, absent-exposure backoff;
5. changed-context retest of each of four movement directions without a ban;
6. duplicate/out-of-order/malformed receipts and provenance mismatch rejection;
7. persistence/reload equivalence, source nonmutation, no branch-feedback;
8. prefix-only inputs, matched branch identity, hidden-field/input rejection,
   split-group disjointness.

Each fixture includes a valid base query and invokes control/candidate once (64
selector calls); malformed-input variants are separate validation assertions on
that fixture and do not require selecting from a rejected input. Structural
assertions may additionally check tables without simulated world transitions.
Across all 64 archived selector contexts, run one unmodified control and one
identity-projection call (128 calls); output equality is required. This is
mechanical parity on known data, never a scientific success endpoint.

Required zero-tolerance gates: original selector source hash, command set and
tie behavior unchanged; row population/order/IDs/feature/action/relation identity
preserved with only the specified measured fields replaceable; valid counted provenance;
cold/no-substitution candidate exactly equals control; command available under
original public enumeration; identical commands produce identical public
outcomes on paired clones; original anchor unchanged after both forks; no
future/evaluation receipt in either evidence input; projection survives JSON
reload with identical selection; deterministic replay from retained artifacts;
no protected source/state mutation. Changed-context fixtures must demonstrate
that a previously blocked direction can be selected again when global evidence
and unchanged selector support it. They cannot force retests in the real corpus.

## Freeze, review and hash order

1. Review this protocol/settings. Obtain implementation authorization. Until then,
   write design artifacts only; do not build L or run any simulations.
2. Implement in a new isolated study source directory. Do not write baseline,
   candidate, authority-work, their state, or existing evidence archives. Read
   frozen modules with bytecode writes disabled; use only small copied recorder
   state or a independently parity-tested public-count accumulator. Never load
   the historical organism or instantiate AgentCore.
3. Verify archived input hashes; reconstruct and freeze L; finish the 32 fixtures
   and 64-input parity check. An independent reviewer verifies the intervention,
   leakage boundary, exact budgets and source parity before held-out execution.
4. Freeze protocol/settings bytes, exclusions, fixture corpus, source/dependency
   manifest and reporting code. Write their SHA-256s plus environment/version and
   review receipt into a pre-execution lock manifest. That manifest has its own
   digest; do not make it self-referential. All six source hashes in settings must
   match, and all additional imported runtime files get explicit hashes.
5. Obtain separate authorization to run this reviewed bounded study. Generate
   the fixed new corpus once. Hash every raw public event and anchor before its
   probe, record both world-clone digests, and append a chained receipt log.
6. Seal complete raw outputs, then unblind/report against the frozen predicates.
   A reporting correction may recompute metrics from unchanged artifacts; bind
   it to a separate reporting hash and explicitly disclose the correction.

The full new corpus cannot honestly be pre-hashed before it exists. Its generator,
seeds, selection rules and budget are frozen first; generated event hashes are
committed before dependent probe outcomes; final corpus/log hashes close the run.

## Retained input format and output ceiling

Persist canonical public records and full selector inputs as deterministic gzip
objects (mtime=0, no filename header), content-addressed by the SHA-256 of their
uncompressed canonical bytes. A compact index records raw/compressed hashes,
lengths, record type and sequence. Identical arm inputs share an object. Verify
the raw hash after decompression before the bounded selector-only audit replay.
This is representation-only storage; no fields or precision may be omitted from
a materialized selector input, and compression may not affect case eligibility.

Stream the neutral public observation/command/receipt log and retain both actual
probe observations/receipts. Do not save a full simulator-history copy at every
anchor. Retain the initial layout seed, neutral command sequence and each
pre-probe world digest, while both actual policy inputs are retained completely
in the compressed object store. Native/hidden simulator internals never enter
policy objects. Full-world reconstruction by replay is not part of the bounded
selector-only audit allowance; it is an independently reproducible data contract,
not additional scientific evidence in this run.

The 64 MiB ceiling applies to actual persisted new study artifacts, including
objects, indexes, logs, fixture/exclusion manifests and reports. Enforce it while
writing, not after building an unbounded in-memory archive. Exceeding it stops
and records an incomplete/invalid result; do not delete evidence, change the
encoding, relax the ceiling or redraw the corpus after outcomes are available.

## Exact budget, resources and stopping

- Old-prefix exclusion reconstruction: 4 x 600 = 2,400 existing-history replay
  transitions, once. No candidate comparison on them.
- Development: 32 synthetic fixtures, 64 archived inputs, exactly 192 selector
  calls; zero additional world transitions.
- Confirmatory neutral corpus: 4 x 1,024 = 4,096 transitions.
- Confirmatory scheduled anchors: 4 x 112 = 448 maximum; each eligible slot uses
  exactly two selector calls and two actual one-step branch transitions.
- Maximum confirmatory branch transitions: 896. No replacement slots.
- Total maximum simulator transitions including legacy replay: **7,392**.
- Maximum development/scientific selector calls: **1,088**. One separately
  budgeted audit pass may rerun each persisted development/scientific selector
  input once: at most **1,088** further calls, **2,176 total**. AgentCore/native
  cycles: **0**.

The actual count is 4,096 + 2N new transitions for N eligible anchors; every
skipped slot has a public pre-decision reason. The one audit pass replays
persisted selector inputs without new transitions and is labelled audit replay,
never additional evidence. Reload/deterministic replay checks use this pass;
do not add unbudgeted selector evaluations. No full benchmark rerun, new seed, longer
horizon, revised split or candidate retry is permitted after outcomes are seen.

Estimate: single-process, CPU-only, approximately 1–5 minutes for these small
worlds; no LLM calls or paid services. Hard ceiling: 10 CPU minutes, 15 wall
minutes, 512 MiB peak RSS and 64 MiB total new study output. These are estimates
and safeguards, not measured runtimes. Process one world at a time. Stream
public triples/compact summaries; retain source hashes and only the necessary
world checkpoints. Do not package full organism state or redundant large archives.

Stop immediately for a source/hash mismatch, malformed provenance, leakage,
unauthorized path write, budget/resource breach or branch-integrity failure.
Record partial counts and an invalid/incomplete result; do not silently retry.
Null, adverse and insufficient-coverage results are terminal for this design.
An infrastructure interruption may resume only from an exact logged checkpoint
after review, with no repeated transition, source/configuration change or unseen
outcome selection; otherwise report incomplete and seek a newly reviewed run.

## Deliverable and interpretation limits

Produce one compact JSON result plus a short report with settings/lock hashes,
coverage/skip counts, all endpoint denominators, projection support, paired
actual outcomes, regressions and terminal classification. Preserve public
receipt-level auditability. Do not create another archive-packaging project.

A pass supports only this frozen conditional-count representation on this finite
off-policy neutral-prefix, one-step corpus. It does not establish autonomous
learning, native agenda choice, inquiry resumption, long-run exploration,
causal world knowledge, source authenticity, ongoing source/feature semantics,
or an ordinary-selection-bound action handoff. Those remain independent gates;
production and new-world activation remain unchanged.
