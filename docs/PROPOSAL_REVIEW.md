# Proposal Evidence Review

Phase 7 reviews self-authored change manifests before any patch authority is considered.

## Problem being solved

A manifest may be perfectly structured and cite genuine evidence while still drawing the wrong engineering conclusion.

A low metric is not automatically a bug. A prediction error is not automatically a replay failure. An unavailable external provider is not automatically defective cognition code.

The review stage asks whether the cited evidence actually identifies the proposed capability layer.

## Verdicts

### supported_problem

Direct evidence demonstrates the relevant behavioral gap.

The proposal may be eligible for future isolated candidate work.

### measurement_gap

The proposal primarily adds measurement or diagnostics. Current evidence does not establish a defect.

Future work, if any, must remain diagnostic-only until direct evidence exists.

### needs_evidence

The proposal's evidence does not yet establish that the proposed code layer is the first incorrect layer.

No patch authority.

## First live case

M000001 targets reproducibility and proposes deterministic replay checks.

Its cited evidence consists of evaluated repository-state predictions/reflections. Those records prove that repository state changed between heartbeats, but the changes correspond to intervening verified code evolution.

They do not show that equivalent deterministic inputs replay differently.

M000001 is therefore a measurement gap, not a confirmed reproducibility defect.

## Review persistence

Reviews have their own IDs and are appended to persistent state.

An unchanged proposal is reviewed once. Subsequent heartbeats reuse the review.

A reviewed unresolved proposal remains the active proposal, so the system cannot bypass a restrictive verdict by immediately producing another manifest.

## Future resolution

For reproducibility, a non-mutating replay diagnostic can create direct evidence.

- equivalent normalized outputs → no demonstrated reproducibility defect;
- divergent normalized outputs → supported_problem evidence.

Only the resulting evidence may change patch authority.
