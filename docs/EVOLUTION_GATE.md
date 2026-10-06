# Evolution Gate

Phase 5 establishes the rules under which future self-modification can be tested.

## Why this comes before patch generation

A system that can modify both its behavior and the tests used to judge that behavior can manufacture the appearance of improvement. AgentTest therefore establishes a preservation judge before allowing self-authored patches.

## Behavioral preservation suite

The initial baseline suite checks observable behavior rather than implementation details:

- state persists across reloads;
- stable observations confirm predictions;
- violated predictions create prediction error and redirect attention;
- unresolved evidence causes reuse of pending work instead of task proliferation;
- supported cognition evidence is accepted and fabricated evidence IDs are rejected;
- semantic memory retains source episode provenance;
- changed world facts preserve superseded claims and evidence links;
- experiment outcomes become provenance-backed world claims.

## Baseline-owned evaluation

For future pull requests the workflow checks out:

- the verified base commit;
- the candidate head.

It then runs the evaluator stored in the BASE commit against both codebases and compares the results with the BASE comparator.

Therefore a candidate cannot make itself pass by editing the evaluator used to judge it.

## Protected paths

Future self-authored change manifests may not target:

- .github/workflows/verify.yml
- scripts/preservation_eval.py
- scripts/compare_eval.py

Changing the evaluation framework remains a separately reviewed governance change.

## Change-manifest contract

A self-authored proposal must declare:

- title;
- target evidence dimension;
- files it expects to change;
- hypothesis;
- expected effect;
- test plan;
- falsification condition;
- rollback;
- existing evidence IDs supporting the proposal;
- baseline target metric.

A proposal without valid evidence references is rejected before patch generation.

## Promotion rule

Passing preservation checks proves only that protected behavior was not observed to regress. It does not prove improvement.

A future candidate must satisfy both:

1. no preserved behavioral regression;
2. positive evidence on the target declared in its manifest.

Until both are true, the candidate is experimental and must not replace the verified baseline.
