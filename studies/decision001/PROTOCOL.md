# Decision Study 001: frozen action-selection comparison

Prospective record: PR #242 comment 6047734476, recorded before study execution.
Owner authorization: Jeremy, 2026-10-07 21:59:33Z.
Frozen implementation: `0ed728dff32e5b4d9ff6aea767710fb7ddb8e836`.
Experienced state: `76cc1f73fae48c774070d7a166abfdfbe9260083`, cycle 1771.

## Question and fixed budget

Does the unchanged Ora 2 selector choose experience that improves one-step
predictive knowledge of the unchanged bounded world more than uniform random
allowed movements? All four commands and full public position remain available.

Run Ora 2 and uniform controllers for paired seeds 0..15 inclusive, 128 executed
world actions per arm, sharing the same one-uniform-draw stream per seed. Run
Phase 41's deterministic `step_planning_lab` reference once, 128 recorded actions
within at most 512 calls. Count idle calls and other-world actions separately.
Do not fabricate independent replicates of the deterministic reference.

This tests action policies, not the full six-command Core lifecycle. Every arm
begins from the exact inherited observations and position. A common unchanged
Ora 2 predictor learns only each arm's actual outcomes. Own choices are distinct
from random/planner exposures. A separate depth-zero observer receives identical
experience and cannot influence action selection. No previous Phase 42 is used.

## Independent, fixed-case evaluation

At 0, 32, 64, 96 and 128 actions, disposable predictor copies answer all 100
position-command queries across the 25-cell approved world. Each position starts
an explicit new observation sequence. The acting model, memory and RNG are not
changed. The evaluator obtains the 100 truths once from the unchanged actuator;
it never sends truths or scores to a controller or trains an evaluation copy.
These 100 oracle queries are not agent actions or experience.

Primary endpoint is average negative log2 probability assigned to the true next
position at 128 actions. Scoring uses a fixed 26-outcome alphabet: the 25 allowed
cells plus an invalid/outside bucket. The evaluator divides the open-vocabulary
predictor's unseen mass equally over not-yet-known cells plus that extra bucket.
Known-cell probabilities are unchanged. This is a scoring convention, not a new
model or supplied world rule. Report initial symbol coverage explicitly.

Secondary descriptive measures: exact top-one known-position accuracy, trapezoid
learning-curve average, loss for cases with fewer than two initial observations,
state-action coverage, newly sampled cases, already-observed blocked actions and
identical-blocked streaks. On-route full-versus-depth-zero pre-outcome losses
measure temporal contribution on actual sequences, separately from grid probes.
Blocked repetition alone is not declared irrational; it is a descriptive count.
The Phase 41 reference is scored through the SAME observer, so this does not
claim to assess its native planner's full learned model or goal utility.

## Decision and stopping rule

Support keeping the current selector for further integration only when its paired
mean endpoint beats uniform by at least 0.02 bits/case AND it wins at least 12 of
16 seeds. Otherwise do not promote it as beneficial. Report every seed and all
ties/losses. Any missing arm, budget failure or integrity/accounting error makes
the primary conclusion invalid. A negative finding does not establish that the
policy cannot help at another budget or in another environment. Seeds are not
independent worlds. No generalization, open-endedness or live milestone claim.

One fixed execution, no result-dependent extensions, tuned seeds, policy changes,
world alterations, manufactured hidden observations or production writes. A failed
run must be diagnosed and recorded; it is not silently rerun. Unit fixtures can
exercise the evaluator but are not the scientific study. All original tracked
bytes are checked before and after the run. All events, evaluations, exact source
identities, summaries and file checksums are preserved in an Actions artifact.

## Execution boundary

Only four files are added: this protocol, the runner, evaluator unit tests, and a
read-only Actions workflow limited to the dedicated study branch. No existing
source, tests, workflows, state, Observer or optional provider configuration is
modified. The dedicated workflow uses no model API, secrets, write token or live
entry point. Its output is outside the checkout. The inherited ordinary CI also
runs; it is not counted as additional study evidence. The study workflow does not
run on PR events or merges into the Ora 2 development branch.

Local evaluator unit tests passed before publication. The full historical files
are unavailable in the local execution environment; actual study execution is
hosted, with exact checkout verification, no substituted miniature origin.
