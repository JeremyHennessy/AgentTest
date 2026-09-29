# Design: Genesis Phases 0–6

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

    persistent evidence + capability metrics
          ↓
    select highest eligible deficit
          ↓
    self-authored CHANGE MANIFEST only
          ↓
    human / later bounded patch mechanism
          ↓
    isolated candidate branch
          ↓
    candidate tests
          ↓
    BASELINE-OWNED preservation evaluator
          ↓
    target evidence + no regressions
          ↓
    verified promotion or rejection

Phase 6 stops at the manifest step. AgentTest still cannot write or merge code.

## Self-authored proposal selection

The proposal engine selects among evidence dimensions with observable deficits. It excludes:

- saturated dimensions;
- adaptation itself, because an unaccepted change is a process outcome rather than a code defect;
- cognition when no cognition provider has produced successful evidence;
- any target for which the organism cannot cite existing evidence.

The chosen manifest records the current target metric, evidence IDs, files, hypothesis, expected effect, test plan, falsification criterion, and rollback.

Only one unresolved self-change proposal may exist at a time. Repeated heartbeats reuse it rather than manufacturing proposal volume.

Creating a proposal does not raise the adaptation metric.

## Governance boundary

A self-authored manifest may not target:

- .github/workflows/verify.yml
- .github/workflows/growth.yml
- scripts/preservation_eval.py
- scripts/compare_eval.py
- src/agenttest/change_control.py

Changes to the rules governing evolution therefore remain outside self-directed mutation.

## Evolution gate

On pull requests, the previous verified BASE commit supplies the behavioral evaluator and comparator used against both baseline and candidate code. A candidate cannot pass by weakening its own judge.

The gate has been tested with a deliberate negative control: a one-line regression changed prediction-error handling from explain_change to reduce_uncertainty. The baseline-owned evaluator detected prediction_error_focus as a regression and rejected that PR.

## Trust ordering

1. Raw sensor observations and explicit outcomes.
2. Derived world claims with source references.
3. Semantic memory used for retrieval.
4. Model-generated candidate thoughts.
5. Self-authored change manifests.
6. Candidate code, once that capability exists.

No lower layer may overwrite the evidence or governance that evaluates it.

## Still missing

- self-authored patch generation;
- target-specific improvement measurement for generated patches;
- broader external perception;
- causal models richer than temporal claim revision;
- independent environmental action;
- measured evidence that optional model cognition improves research outcomes;
- any evidence of subjective experience.
