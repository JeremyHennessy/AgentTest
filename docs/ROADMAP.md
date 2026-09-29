# Research Roadmap

This roadmap is hypothesis-driven. A phase advances only when its predecessor produces reproducible evidence.

## Phase 0 — Persistence — verified baseline

Persistent state, episodic memory, questions, experiments, reflection, and immutable history.

## Phase 1 — Perception — verified baseline

Auditable repository sensing and explicit surprise detection.

## Phase 2 — Predictive drives — verified behavior

Predictions are evaluated against later observations, and prediction error changes attention.

## Phase 3 — Grounded generative cognition — verified boundary

The optional cognition provider is structurally gated, has no tools, cannot alter evidence directly, rejects unknown evidence references, and fails closed when no provider is configured.

No API key is currently configured, so live cognition attempts are recorded as unavailable rather than simulated.

## Phase 4 — Semantic memory and temporal world model — verified baseline

Semantic memory consolidates repeated concepts and associations while preserving source episode IDs. The temporal claim ledger preserves superseded facts and links derived claims to raw evidence.

The live autonomous branch migrated to schema v5 without losing prior history.

## Phase 5 — Evolution preservation gate — verified

The behavioral gate uses the previous verified BASE commit's evaluator against both baseline and candidate code.

A deliberate negative-control PR introduced a known prediction-error regression. Both the candidate suite and the base-owned comparison rejected it; the base comparator explicitly reported prediction_error_focus as the regression. The bad PR was closed without merge.

## Phase 6 — Self-authored change manifests — implementation under verification

AgentTest may select an evidence-backed capability deficit and author one change manifest. It still cannot edit code.

Constraints:

- valid existing evidence IDs are required;
- externally blocked cognition is not misdiagnosed as a code defect;
- adaptation is not inflated by proposal creation;
- one unresolved proposal is reused instead of generating proposal spam;
- governance/evaluator files cannot be targeted;
- every manifest includes baseline metric, expected effect, test, falsifier, and rollback.

The autonomous heartbeat will persist state/next_change.json after this phase is verified.

## Phase 7 — Proposal evaluation

Measure proposal quality before allowing patches: evidence relevance, target correctness, testability, duplication, and whether proposed interventions actually address the first incorrect layer.

## Phase 8 — Isolated self-authored patches

Only after proposal quality is demonstrated, permit bounded patch generation on candidate branches. No automatic promotion. Every patch must pass the base-owned preservation gate and demonstrate positive evidence on its declared target.

## Phase 9 — Broader world interaction

Add narrowly scoped external sensors and actions with explicit permissions, provenance, rate limits, and outcome verification.

## Phase 10 — Open-ended research

Maintain a frontier of unresolved questions and select among them using expected information gain and evidence debt.

## Phase 11 — Emergent identity study

Only after substantial persistent history exists, test whether identity-like continuity emerges from memory, prediction, self-modeling, and internally selected goals.

No phase is permitted to assume consciousness in advance.
