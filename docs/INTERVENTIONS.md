# Intervention-Aware Prediction

## Problem

A stability prediction is only testable while its prediction context remains applicable.

AgentTest previously stored the phrase "unless an intervening change occurs" in each repository prediction, but did not represent that condition computationally. Verified code evolution therefore appeared as repeated prediction failure.

## Baseline fingerprint

repository-v2 adds baseline_fingerprint.

It is a SHA-256-derived fingerprint over every tracked file outside state/.

The state directory is excluded because autonomous experience is expected to change there.

## Evaluation

When evaluating a pending repository prediction:

1. Compare expected and observed baseline_fingerprint.
2. If they differ, mark the prediction invalidated_by_intervention.
3. Preserve the fingerprint difference and a reflection.
4. Do not score prediction_error.
5. If fingerprints match, evaluate all comparable fields normally.

## What this does not claim

A fingerprint difference does not identify the actor, cause, quality, or intention of a change.

It establishes only that the non-state repository context differs from the context in which the earlier prediction was made.

## Why this is more falsifiable

The organism can now separately test:

- whether stable code yields stable observations;
- whether unexpected runtime/state changes occur under the same code;
- whether its own changing implementation altered the context enough to invalidate earlier expectations.

This prevents self-development activity from automatically dominating the error signal.
