# Design: Genesis Phases 0–8

## Premise

AgentTest is an original experiment in persistent adaptive computation. It is not an imported agent framework and it does not use a scalar alive score.

## Adaptive loop

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

## Evolution evidence loop

    evidence + capability metrics
          ↓
    self-authored change manifest
          ↓
    proposal evidence review
          ↓
    ┌──────────────────┬──────────────────┬─────────────────┐
    │supported_problem │measurement_gap   │needs_evidence   │
    │candidate possible│diagnostic only   │no authority     │
    └──────────────────┴──────────────────┴─────────────────┘
                              ↓
                     VERIFIED diagnostic
                              ↓
                  ┌───────────┴───────────┐
                  │                       │
             divergence                stable
                  │                       │
          supported_problem       no_problem_observed
                  │                       │
       future candidate patch          close proposal

## Diagnostics are part of the judge

A self-authored candidate must never be able to write the diagnostic that proves its own problem exists.

The following are therefore governance-protected:

- .github/workflows/verify.yml
- .github/workflows/growth.yml
- scripts/preservation_eval.py
- scripts/compare_eval.py
- src/agenttest/change_control.py
- src/agenttest/proposal_review.py
- src/agenttest/self_proposal.py
- src/agenttest/diagnostics.py
- src/agenttest/diagnostic_replay.py

Future changes to those files are governance changes and require separately reviewed development.

## Deterministic replay diagnostic

The first verified diagnostic addresses M000001's reproducibility measurement gap.

It runs an identical controlled sequence twice against separate temporary StateStore instances. The sequence exercises:

- repeated and changed repository observations;
- prediction confirmation and violation;
- intention selection;
- episodic and semantic memory;
- world-model updates;
- experiment selection;
- explicit experiment outcome recording;
- journal persistence.

Only volatile timestamp fields are replaced during normalization. Identifiers, ordering, evidence relationships, metrics, questions, experiments, world claims, semantic memory, and journal structure remain compared.

The result contains two normalized digests and the first exact structural difference, if one exists.

## Review refresh

Proposal reviews are evidence-versioned.

An existing review is reused while its set of completed diagnostics is unchanged. Once a new completed diagnostic exists, review_change_proposal performs a new classification and records which diagnostic IDs were considered.

This prevents both review churn and stale conclusions.

## New verdict: no_problem_observed

A clean diagnostic does not prove perfection. It says the requested controlled test found no evidence for the proposed defect.

That verdict:

- grants no patch authority;
- closes the current proposal;
- preserves the diagnostic as evidence;
- can raise an evidence-derived capability metric when appropriate.

## Trust ordering

1. Raw sensor observations and explicit outcomes.
2. Verified diagnostic results.
3. Derived world claims with provenance.
4. Semantic summaries used for retrieval.
5. Model-generated candidate thoughts.
6. Self-authored change manifests.
7. Candidate code.

Lower-authority layers cannot rewrite the evidence or judges above them.

## Still missing

- self-authored bounded patch generation;
- target-specific evidence comparison for candidate patches;
- broader external perception;
- independent environmental action;
- successful live model-backed cognition evidence;
- evidence of subjective experience.
