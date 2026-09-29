# Design: Genesis Phases 0–7

## Premise

AgentTest is an original experiment in persistent adaptive computation. It is not an imported agent framework and it does not use a scalar alive score.

## Current adaptive loop

    auditable perception
          ↓
    episodic memory ───────────────→ semantic consolidation
          ↓                              ↓
    prediction evaluation          concept associations
          ↓                              ↓
    temporal world claims ←──── observed facts / outcomes
          ↓
    internal drives
          ↓
    chosen intention
          ↓
    optional grounded cognition
          ↓
    question → experiment → prediction
          ↓
       next heartbeat

## Evolution loop

    evidence + capability metrics
          ↓
    self-authored change manifest
          ↓
    proposal evidence review
          ↓
    ┌───────────────┬────────────────────┬─────────────────┐
    │supported      │measurement gap     │needs evidence   │
    │problem        │diagnostic only     │no patch         │
    └───────────────┴────────────────────┴─────────────────┘
          ↓
    future isolated candidate work
          ↓
    BASELINE-OWNED preservation evaluator
          ↓
    target evidence + no regressions
          ↓
    verified promotion or rejection

Phase 7 still stops before code generation.

## Why valid evidence is not enough

A change manifest can cite real evidence while still targeting the wrong layer.

For example, the first live self-authored manifest M000001 proposed deterministic replay checks because reproducibility was 0.8. Its evidence references were genuine prediction evaluations, but those observations did not demonstrate replay divergence.

Phase 7 therefore separates:

- evidence existence;
- evidence relevance;
- evidence that identifies a behavioral defect;
- evidence that only identifies a measurement gap.

## Proposal review verdicts

### supported_problem

Direct evidence connects the observed problem to the proposed capability layer.

This may eventually permit an isolated candidate patch, but still does not prove the proposed implementation is correct.

### measurement_gap

The proposal would add measurement, diagnostics, or traceability, but current evidence does not establish that underlying behavior is wrong.

Future authority is limited to diagnostic work.

### needs_evidence

The evidence is real, but it does not identify the proposed code surface as the first incorrect layer.

No patch authority is granted.

## Current direct-evidence rules

The initial conservative rules intentionally cover only cases that can be justified from current evidence:

- reproducibility requires a completed deterministic-replay diagnostic reporting divergence before it becomes a supported defect;
- learning can be supported when a pending experiment remains unresolved despite later prediction-evaluation evidence;
- reflection can be supported when the same evidence-backed lesson repeats;
- cognition cannot be diagnosed as a code problem without a successful provider attempt;
- selected measurement-oriented capabilities remain diagnostic-only without direct failure evidence.

Unknown cases default to needs_evidence.

## Anti-proliferation

A proposal remains active after review while unresolved. Heartbeats cannot evade an inconvenient review by generating another proposal.

Reviews are idempotent: re-reviewing an unchanged proposal reuses the existing review.

## Governance and preservation

Self-authored manifests still cannot target:

- .github/workflows/verify.yml
- .github/workflows/growth.yml
- scripts/preservation_eval.py
- scripts/compare_eval.py
- src/agenttest/change_control.py

The base-owned preservation gate remains authoritative for candidate code.

## Still missing

- non-mutating diagnostics generated from measurement-gap reviews;
- self-authored patch generation;
- target-specific improvement evaluation for generated patches;
- broader external perception;
- independent environmental action;
- evidence of subjective experience.
