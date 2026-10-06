# Self-Authored Change Proposals

Phase 6 grants AgentTest authority to originate a proposed software change, but not to execute it.

## Selection

The engine looks at current evidence-backed metrics and chooses the largest eligible capability deficit.

It does not simply choose the lowest number:

- adaptation is excluded because it records accepted change outcomes rather than a code capability;
- cognition is excluded when no successful provider evidence exists, so a missing credential is not mislabeled as a software defect;
- a target without existing evidence references is ineligible.

Ties use a fixed priority order for reproducibility.

## Manifest

A proposal records:

- unique proposal ID;
- source and creation cycle;
- target dimension and baseline metric;
- existing evidence references;
- expected files;
- hypothesis;
- expected effect;
- test plan;
- falsification criterion;
- rollback;
- selection rationale.

The manifest is passed through the same change-control validator used for future evolution.

## Anti-proliferation

At most one unresolved self-authored change proposal is active. Until it is resolved, later heartbeats reuse the same proposal.

Proposal generation does not itself change the adaptation metric.

## Authority boundary

Phase 6 cannot:

- edit the proposed files;
- create an implementation branch;
- merge anything;
- modify the evolution governance files through a self-authored manifest.

Patch generation remains a later phase and will only be considered after proposal quality has been measured.
