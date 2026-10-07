# Copied challenge inquiry/source compatibility

Research-only executor hardening. No live activation, Core attention change,
new observation source, source adapter, or new-world readiness claim.

## Defect reproduced

The challenge executor already validated its own source/descriptor and the
recorder's source/descriptor. Public inquiry staging validated a publication
against its supplied manifest. These checks did not bind the staged inquiry to
the particular recorder/executor used for capability issuance.

On isolated copies, staging an internally consistent different source ID or
incompatible observation schema succeeded, and the executor issued a capability.
An unknown feature, including a source-bound `pub.<hash>` feature from the separate
public-inlet namespace, also acquired a capability: the unchanged selector treated
missing association keys as legitimate zero-sample exploration.

This was an executor admission gap. It was not evidence for changing priorities,
strict waiting governance, or the planner. The public inlet and challenge recorder
use different feature semantics; this patch does not translate between them.

## Narrow guard

Before issue and execute can mutate any copied store, a pure guard reconstructs
the canonical current recorder publication and checks:

- One uniquely identified proposed experiment awaiting native evidence.
- A feature known in the recorder's retained temporal totals.
- That feature is observable in the current public observation.
- Exact expected candidate identity, native version, relation, objective and score.
- One uniquely identified owned question with matching native identity and refs.
- One uniquely identified cited native evidence episode whose complete canonical
  payload matches the reconstructed publication, including full source-prefixed
  observation refs and temporal counts.

The expected candidate identity is recomputed using the canonical reviewed
manifest/schema and current publication. Its abbreviated hash components are not
used alone: the complete grounded payload and question binding must also match.
Existing recorder/executor identity, source-content hash, freshness, single-use,
restart and action-budget checks remain in place. No evidence is staged, repaired,
or resealed by the guard. No persistent schema or token version changes are needed.

This intentionally accepts the existing research workflow's exact current
publication. It does not assert support for arbitrary older pending inquiries,
other sources, differently serialized grounding, or a generic inlet-to-executor
bridge. An older inquiry that cannot be reconstructed conservatively fails closed.
These unsigned local integrity checks do not authenticate an external source or
protect against a hostile process rewriting the entire research state.

Unknown features and known-but-currently-unobservable features have distinct
rejection reasons. An unavailable feature leaves the inquiry pending, without an
outcome, reflection, capability or world transition. Absence is never refutation.
Legitimate undersampled actions for a compatible observable feature remain valid;
the selector, scores and tie order are unchanged.

## Verification

The new focused controls reproduce source ID, schema, recorder-version,
unknown-feature, public-inlet-feature, grounding and ownership failures before
the repair. They then verify issue/execute rejection preserves Ora, recorder and
executor bytes. Execution is tested separately using an explicitly labelled
synthetic issuer bypass; this bypass exists only in the test.

A known occluded feature is tested separately from an unknown one. A positive
old-format staged inquiry retains legitimate undersampling, succeeds once after
executor restart, and preserves replay and exhausted-budget rejection. The existing
freshness and multi-action tests are retained unchanged.

Final validation at this source: 427 repository tests pass and the unchanged
behavioral preservation suite passes 30/30. A separate bounded developer-control
comparison used twelve ordinary research fixture transitions and one capability
per arm. Baseline/candidate selection, receipt, observation, resulting world and
consumption counts were exactly equal; Ora and recorder bytes were unchanged.
Token hashes and copied-store paths were intentionally not compared because the
reviewed source hash and temporary paths necessarily differ.

No full scientific study was rerun or extended. Existing negative attention and
native-selection findings are unchanged. The first test draft attempted to persist
a duplicate episode; the existing StateStore already rejected it. The final control
asserts that stronger earlier boundary rather than bypassing it. Initial failure
and corrected validation logs remain in the separate review evidence.
