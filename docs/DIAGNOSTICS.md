# Verified Evidence Diagnostics

Diagnostics resolve uncertainty without granting a candidate authority to manufacture its own evidence.

## Core rule

Diagnostic code used to authorize future patches belongs to the verified governance surface.

Self-authored change manifests may request a diagnostic, but may not modify:

- src/agenttest/diagnostics.py
- src/agenttest/diagnostic_replay.py
- src/agenttest/proposal_review.py
- src/agenttest/self_proposal.py
- src/agenttest/change_control.py
- preservation workflows or evaluators.

## Deterministic replay v1

The reproducibility diagnostic runs the same controlled adaptive sequence twice in separate temporary directories.

It normalizes only:

- created_at
- updated_at
- time
- observed_at
- evaluated_at
- completed_at

Everything else remains part of the equality check.

A stable result records:

- outcome=stable;
- two equal normalized SHA-256 digests;
- no first_difference;
- mutation_scope=isolated_temp_state;
- source_state_mutated=false.

A divergent result records the first structural path where the normalized runs differ.

## Evidence effect

After a diagnostic is completed, the proposal is reviewed again.

For reproducibility:

- divergent → supported_problem / candidate_allowed;
- stable → no_problem_observed / no patch authority;
- no diagnostic → measurement_gap / diagnostic_only.

A stable replay is positive evidence for the reproducibility capability and can raise its metric on the next adaptive cycle.

## Interpretation

Stable replay does not prove the entire system is universally reproducible. It supports the narrower claim that the verified controlled fixture reproduced equivalent normalized behavior under the tested conditions.
