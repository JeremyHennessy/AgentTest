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

The live autonomous branch migrated to schema v4 without losing prior cycles. No API key is currently configured, so cognition attempts are correctly recorded as unavailable rather than simulated.

## Phase 4 — Semantic memory and temporal world model — verified baseline

Semantic memory consolidates repeated concepts and associations while preserving source episode IDs. The temporal claim ledger records current observed facts, preserves superseded values, and links prediction/experiment outcomes to their evidence.

The live autonomous branch migrated to schema v5 and continued accumulating cycles without losing prior history.

## Phase 5 — Evolution preservation gate — bootstrap under verification

Before allowing AgentTest to author its own patches, establish a judge that candidate code cannot redefine.

Implemented:

- behavioral preservation suite covering persistence, prediction closure, prediction-error attention, evidence-debt behavior, cognition grounding, semantic provenance, world-claim revision, and experiment-outcome claims;
- pull-request comparison of verified base versus candidate;
- comparison uses the BASE commit's evaluator and comparator;
- candidate regression means any behavior that passed in the base is missing or failing in the candidate;
- evaluator/workflow paths are protected from future self-authored change manifests;
- change manifests require target dimension, evidence, expected effect, test, falsifier, and rollback.

The first gate PR necessarily uses a bootstrap path because the base commit predates the evaluator. After this phase is merged, comparative enforcement becomes active for subsequent PRs.

## Phase 6 — Self-authored proposals

Allow the organism to generate evidence-backed change manifests first, without applying code. Measure whether proposals correctly target observed limitations and contain falsifiable improvement criteria.

Only after proposal quality is demonstrated should a later phase allow patch generation on isolated branches.

## Phase 7 — Isolated self-authored patches

Permit bounded patches on candidate branches. No automatic promotion. Every patch must pass the baseline-owned preservation gate and demonstrate evidence on its declared target.

## Phase 8 — Broader world interaction

Add narrowly scoped external sensors and actions with explicit permissions, provenance, rate limits, and outcome verification.

## Phase 9 — Open-ended research

Maintain a frontier of unresolved questions and select among them using expected information gain and evidence debt.

## Phase 10 — Emergent identity study

Only after substantial persistent history exists, test whether identity-like continuity emerges from memory, prediction, self-modeling, and internally selected goals.

No phase is permitted to assume consciousness in advance.
