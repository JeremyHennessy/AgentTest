# Design: Genesis Phases 0–9

## Premise

AgentTest is an original experiment in persistent adaptive computation. It does not use a scalar alive score and does not equate model fluency with evidence.

## Adaptive loop

    auditable perception
          ↓
    prediction scope check
          ↓
    ┌───────────────────────┬──────────────────────────┐
    │same baseline          │baseline intervention     │
    │evaluate prediction    │invalidate old prediction │
    └───────────────────────┴──────────────────────────┘
          ↓
    episodic + semantic memory
          ↓
    temporal world claims
          ↓
    internal drives
          ↓
    chosen intention
          ↓
    optional grounded cognition
          ↓
    question → experiment → next prediction

## Why intervention awareness matters

A prediction is meaningful only inside the conditions under which it was made.

The repository-stability prediction says measured repository state should remain stable unless an intervening change occurs. Earlier versions recorded the caveat in prose but did not implement it: every verified code merge changed file counts/source lines and was scored as a prediction error.

Phase 9 makes the scope explicit.

## Baseline fingerprint

The repository sensor computes baseline_fingerprint from the ordered path and bytes of every tracked non-state file.

Excluded:

- state/ and all descendants.

Included:

- runtime code;
- tests;
- workflows;
- documentation;
- configuration;
- other tracked repository files.

This fingerprint answers a narrow question: did the non-persistent repository baseline change?

It does not infer who changed it, why it changed, whether the change was good, or whether it was verified.

## Prediction outcomes

### confirmed
The baseline fingerprint is unchanged and all comparable measurements match.

### violated
The baseline fingerprint is unchanged but one or more comparable measurements differ.

This creates prediction-error pressure.

### invalidated_by_intervention
The non-state baseline fingerprint changed.

The old stability prediction is no longer treated as a fair test of the new baseline. The intervention and reflection are preserved, but prediction_error is zero for that result.

## Surprises versus errors

A repository intervention can still create a surprise record. Surprise means an observed state changed.

Prediction error is narrower: an expectation failed inside an unchanged prediction scope.

The drive system no longer automatically treats an intervention surprise as prediction failure.

## Evidence and world model

invalidated_by_intervention is retained as a prediction-evaluation world claim, preserving the fact that the prediction became inapplicable rather than silently discarding it.

## Governance

Intervention awareness does not weaken the preservation gate. Candidate code must still pass every behavior that the previous verified base could demonstrate.

## Still missing

- isolated self-authored candidate patches;
- target-specific candidate improvement evidence;
- broader external perception and action;
- live successful model cognition;
- evidence of subjective experience.
