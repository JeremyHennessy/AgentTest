# Finite grounded investigation policy and reviewed API seam

Proposal v2, 2026-10-07. All algorithms below are specifications, not implemented
or executed results. Keep #222 and the production source intact as controls.

## 1. The scientific unit

A proposed inquiry asks: given this exact public context and available movement
command, which of these observation-derived explanations best predicts the next
public position? It owns one context-local experiment. A bounded policy chooses
among the inquiries; the external caller cannot choose the winner.

This is modest model induction inside an authored finite language. The agent
infers parameters, conditions and competing explanations from observations; it
does not select a supplied list of goals or receive a desired world state. The
language itself is a human design choice. Discoveries outside that language are
not representable, and program enumeration is not evidence of useful discovery.

## 2. Public inputs and context

Use the exact existing validated Challenge observations and receipts:

- Observation: `world_version`, `observation_id`, `cycle`, `position`,
  `inventory_ids`, `visible_entities`.
- Entity: `id`, `position`, `appearance`, optional `observable_state`.
- Receipt: `id`, `cycle`, `action`, `target`, `direction`, `before`, `after`,
  `success`, `blocked`, `observed_effects`, `visible_entity_states`, optional
  `inspection`.

Preserve complete source frames/receipts for authority and audit. The policy's
numeric input is a deliberately smaller allowlisted projection. Its context C is
the canonical map returned by `public_features`: position, sorted inventory and
visible identities, visible entity positions and available observable states.
Missing fields are explicit missing values, not empty values or refutations.
Appearance prose, source display names, observation IDs, receipt IDs, timestamps,
cycle numbers and citation counts do not enter a score or feature predicate.
Opaque IDs only establish equality/continuity; lexical ID spelling is not a
feature, tie breaker or source of reward. Sorting is canonicalization, not rank.

The initial action scope is the four exact movement command objects already
returned by `candidate_commands(observation)`: north/east/south/west, with no
target or direction fields. This intentionally excludes the five other existing
action kinds from this first scientific claim. No invented action or private
affordance is added. The executor still validates membership in the original
public command list. Each attempted move, including blocked, costs one action.

Policies never receive `_kind`, `_mass`, `_carryable`, `_movable`, `_latched`,
`_required_object`, `_gate`, layout ID, private entity maps, transition functions,
future sensor values, evaluator branches or scorer feedback.

## 3. Data-derived, immutable explanatory cohort

The discovery prefix D is fixed before the experimental evidence interval U.
Only D constructs the common model cohort. Each rule has exact input frame and
receipt references, its derivation, code version and a canonical structural ID.

For each movement action a:

1. Extract actually observed displacement pairs from D: receipt/observation
   `after - before`, with action identity verified against that receipt.
2. The first model class permits zero displacement and one distinct observed
   nonzero displacement d. Both must have been observed for a. If not, a has
   `insufficient_explanatory_diversity`; if more than one distinct nonzero delta
   exists, it has `outside_first_model_class`. Never invent an orientation from
   the simulator's movement table or turn an unknown into an executable inquiry.
3. Generate the two constant displacement rules, whose delta parameters come
   from those observations. Enumerate one-condition rules: “if g equals v,
   displacement d1; otherwise d2.” Here g is one of the three top-level public
   fields position, inventory_ids, visible_ids; v is an observed pre-action value
   in D; d1/d2 are the two observed deltas, and d1 != d2. Both
   predicate branches must have at least one supporting D record for their
   assigned outcome. Inventory/visible sets use opaque identity equality only,
   never a special interpretation of an ID. Entity-specific position/state
   predicates are outside this first language, although those fields remain
   part of the full exact context used for evidence matching.
4. Enumerate no more than 128 source-grounded conditional rules per action.
   Overflow makes that action `generator_capacity_exhausted`, with no truncation
   based on a scientific outcome. Among a complete enumeration, retain the two
   constants plus the best five conditional rules (or fewer), ordered by D
   construction loss, then syntax length, then canonical structure. Construction
   loss is wrong predictions plus unavailable predictions across all D records
   of a; an abstention is not credited as a correct prediction. This ordering
   penalty does not turn missingness into evidence against a hypothesis. Canonical
   structure uses the fixed field order position, inventory_ids, visible_ids;
   within each field values are ordered by their first chronological D occurrence,
   and deltas by their first D receipt occurrence. Each field has one value per
   frame, so no simultaneous-feature/entity tie needs an ID-spelling tie breaker.
   Canonical JSON key order and label spelling cannot decide which rules survive.
   This is an explicit finite inductive bias, not a bonus or success metric.
5. Add a named unresolved-process model N, which assigns equal probability to
   three observable outcome classes: zero displacement, displacement d, other.
   N is an uncertainty safeguard, not an inferred explanatory discovery. Total
   models per action are 3–8. Freeze the model definitions once; U/E1 never generates
   or edits a rule, changes a predicate, or adds a hypothesis.

The model language cannot express entity-field predicates, multiple conditions, hidden mechanisms,
multi-step interventions, causal direction, delayed effects, changing semantics,
arbitrary numerical functions, new features or new actions. Correlated public
conditions are candidate explanations, not established causal mechanisms.
No rule is “true” because it fits its construction prefix.

At each anchor, compile the cohort for action a against current C into static
position predictions: current position plus the rule's predicted delta. A missing
predicate field or invalid public-position output makes that rule unavailable
for that context; missing predicates do not evaluate to false. Do not
replace them with the correct blocked outcome. An action needs at least two
available concrete rules predicting different positions. If fewer remain, it
cannot own a discriminating test. At most one inquiry per action is admitted.
Its concrete compiled hypotheses remain immutable until that one-step case
finishes. N is retained only in the forecasting receipt; it has no categorical
claim that #222 could truthfully mark supported or contradicted.

Availability is decided from the frozen cohort and current C before evidence
weighting. Remove unavailable concrete models from that context's forecasting
set in both arms, then use the uniform prior over remaining concrete models plus
N and apply eligible likelihood updates. Unavailable models receive no weight,
likelihood credit or denominator contribution for that context; their definitions
remain in the immutable source cohort. One or more available concrete models is
enough for a forecast and F membership; zero concrete models means no forecast
and exclusion from F with an explicit coverage reason. Two available concrete
models with distinct positions are needed for action-bearing inquiry admission.
Thus N alone cannot manufacture a forecastable case or a discriminating test.
Equal C/cohort yields the same availability in both arms regardless of masking
or realized probe outcomes.

This compilation is a **new reviewed admission contract**, not a trick for
mutating #222's immutable hypotheses. Every case hypothesis points to its frozen
source model, derivation refs, exact C and command. Generating a later case at
another C is a new independent case, not a claimed successor or resumption.
There is no cross-case inquiry identity migration in the first experiment.

## 4. Evidence, forecasts and selecting a distinguishing test

The initial weight over each action's available concrete models plus N is uniform.
Use only eligible post-D public evidence records with exactly the same public C
and action a to update weights. The protocol supplies common neutral U to both
arms, then retains or masks one owned event E1 at the second decision.
No comparison of learning progress between an easy context and a hard context is
allowed. D already supplied model construction; do not count D again as U.

For each of the three outcome classes, a concrete rule assigns probability 0.95
to its predicted displacement class and 0.025 to each other class. N assigns
1/3 to each. These are frozen modeling assumptions, not calibrated probabilities
or simulator noise estimates. Update weights by the product of likelihoods of
unique eligible evidence events, normalizing exactly once per event. Use exact
rational arithmetic for priors, likelihoods, weights, forecasts and Brier loss;
0.95 = 38/40 and 0.025 = 1/40. Persist reduced canonical numerator/positive-
denominator pairs as decimal strings. Enforce a 256-decimal-digit bound per
component and reject overflow without a decision. Entropy alone uses 50-digit
Decimal logarithms and is serialized rounded half-even to 18 decimal places;
apply the 0.01-bit threshold and 1e-12 tie tolerance to those frozen values.
Missing/invalid evidence never updates weights. Keep the full posterior and
mixture distribution in the pre-action decision receipt. A forecast is not a new
global hypothesis truth value and does not rewrite T3's case-local verdict.

For current C, let p_h(y|a,C) be those model distributions and w_h the weights.
Score each eligible inquiry by predictive disagreement:

I(a,C) = H(sum_h w_h p_h) - sum_h w_h H(p_h), in bits.

This is expected information about the finite model index under its declared
assumptions. It is not raw surprise or prediction error. All action costs here
are one, so there is no tunable curiosity/citation/count/source reward and no
cost bonus. Choose the highest I greater than 0.01 bits; ties within 1e-12 use
the existing north/east/south/west order. If none qualifies, select null. Freeze
the complete <=4 inquiry menu, all scores, eligibility reasons, chosen owner,
command, per-model predictions and mixture forecast before any action.

One high error is not a reason to repeat forever. Under recurring unpredictable
outcomes, the unresolved-process model can dominate and between-model
disagreement falls, even when outcome entropy stays high. This design does not
prove immunity to all noisy distractors. Required policy-only fixtures include
alternating/noisy outcomes, contradictory evidence and all-model misspecification;
the scientific run uses an unchanged deterministic world and cannot establish a
general noise-robustness result. Report unresolved-model mass and nulls. A new
language or hypothesis set following misspecification is explicitly deferred.

Context changes permit retesting: C changes, so old local likelihoods do not
transfer as if they came from the new C. No permanent blocked-command blacklist
exists. Once a newly changed context is actually observed, its new evidence may
change weights. Resetting uncertainty through source renaming or duplicate
delivery is forbidden; changing an irrelevant field also does not fabricate a
new source or new receipt, though exact C can fragment experience. That known
over-specificity is a limitation to measure, not silently repair during a run.

## 5. Replace the bridge without replacing ownership with a caller instruction

#222 cannot presently host this policy unchanged:

- Admission reconstructs `selected_temporal_candidate` from the old single
  ranked recorder publication. A grounded feature menu is not accepted.
- `select_next` calls ordinary Core and demands its actual returned experiment.
- Static predictions are copied verbatim from the immutable hypothesis set.
- The validator expects full legacy bridge state and canonical legacy meaning.

First make a separately reviewed **default-off research API v2**, not an
in-place reinterpretation of v1. Preserve v1 capsule reopening through its exact
unchanged frozen-source execution environment, not an in-place upgrade. #222 pins all production Python
and every Python file in its inquiry_executive package; adding or editing files
inside that closure changes the expected manifest and old capsules must reject
it. Place v2 in a separately versioned research package/checkout with its own
complete pinned closure. Never monkeypatch the v1 validator or run_cycle, widen
its source acceptlist, or auto-migrate a v1 capsule. No changes to production
Core, ranking, schema, workflows, default flags or live state are needed.

Two explicit components are necessary:

1. Grounded proposal admission: internally construct the bounded model cohort
   from verified public D; admit a current-context case with its immutable
   compiled predictions and original frame/receipt derivations. Validate exact
   source descriptor, schema, observation/receipt chain, actor/world/run,
   available feature and command, generated-model digest and derivation. The
   old ranked-publication identity cannot stand in for this proof. A separate
   validator version must demonstrate equivalent fail-closed source/authority
   obligations without claiming semantic equivalence to native legacy ranking.
2. An internal `SelectionReceipt` producer: a pinned backend runs once inside
   T1 on the validated allowlisted view, with no world hook. It returns a
   complete menu, one selected inquiry/owned experiment pair or null, exact
   command/predictions, input view digest and policy state delta. A caller may
   choose a reviewed backend at capsule creation but cannot supply a receipt,
   winner, experiment, score, callback, forced-resume flag or per-decision policy.

The receipt envelope is policy-independent: schema version, backend/code hash,
run/revision/decision IDs, source/frame/context hashes, proposal-manifest digest,
full bounded candidate menu and reasons, unique selected inquiry/experiment or
null, immutable hypothesis/derivation hash, forecast, exact command, predecessor
and policy-state hashes. Creation locks backend identity. Its producer identity
is checked in addition to its bytes; an externally constructed hash is not
selection authority. A pure receipt verifier independently reconstructs derivation
refs and model bodies from D, current-context availability, the exact eligible
unique-evidence set, posterior weights, all forecasts, all I scores, and the
threshold/tie-aware argmax or null predicate. Every disclosed menu entry and the
committed selection must equal that unique expected result. This verifier does
not call the backend again, mutate policy state, issue authority, select a
substitute or replay an action. Inconsistent receipts reject unchanged: this is
a deterministic proof check, not another selection opportunity. Execution refers
to the original committed receipt and selected owner only. V2's manifest includes
the generator, projection/mask, numerical library versions, verifier, backend and
complete executor/adapter dependency closure.

An adapter for legacy Core may emit this common envelope while retaining its
actual result/event/post-state proof. It must still show B's generic experiment
as unowned, and its bounded legacy candidate summary as incomplete. The new
backend has an exact <=4 menu and owns the experiment it selects; it does not
fabricate a Core cycle, question or legacy routing success. Label every result
`selection_backend=grounded_policy_v2`, never ordinary Core selection.

## 6. Transaction and API acceptance boundary

Reuse the tested T1/T2/T3 obligations: latest internal selection -> one prepared
attempt -> one pure copied transition and full durable outcome -> one canonical
case-local interpretation. Preserve source-only pinned loading, original copied
input checks, stable locks, CAS, atomic replacement/fsync, full outcomes, exact
budget consumption, cancellation, restart validation, conservative reservation,
no outcome replay and no interpretation-by-new-rule credit. The extra proposal,
menu and forecasts require a new complete serialized-size proof; #222's byte
proof does not automatically cover them.

Before any scientific run, an independent implementation review must close:

- V1 parity and all prior negative controls; unsupported backends/schema reject.
- Receipt forgery, caller-selected owner, current owner/command drift, wrong
  source/derivation, unrelated experiment, duplicate evidence, stale revision,
  missing feature, missing context and incomplete model cohort all fail closed.
- Policy view privacy before generation, selection, prediction and update;
  blocked/null/cancelled/restarted flows do not expose private state.
- Full actual candidate disclosure for v2; v1 incompleteness remains explicit.
- Same-source duplicate delivery has no learning/selection effect; changed-body
  duplicate and unknown source IDs reject. Display label and consistent opaque
  identifier alpha-renaming preserve policy outputs up to that same renaming.
  Authority tests must still reject unauthorized actual SOURCE_ID substitutions;
  “label invariance” cannot waive source validation.
- Changed public contexts can legitimately retest; missingness is not evidence;
  noisy repeated error does not become an ever-increasing action score.
- Matched-lifecycle evidence masking cannot be undone through frames, receipts,
  posterior caches, recorder counts, candidate summaries or paths.
- New-envelope byte bounds, no-capacity nulls and protected T2/T3 completion.

Hypothesis-set extension, version migration, linked successors, adding features,
adapting model structure after D and cross-context durable learned programs all
require a separate reviewed API step and a later scientific comparison. They
are not smuggled into the receipt refactor. This proposal retains one immutable
set of concrete case hypotheses per inquiry and one canonical outcome verdict.
