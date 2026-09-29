# Design: Genesis Phases 0–4

## Premise

AgentTest is an original experiment in persistent adaptive computation. It is not an imported agent framework and it does not use a scalar alive score.

## Current loop

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

## Episodic versus semantic memory

Raw episodes remain immutable evidence. Semantic memory is a derived index over those episodes.

Each concept records occurrence count, first/last cycle, and source episode IDs. Co-occurring concepts create deterministic association edges with their own source episode IDs.

Consolidation is incremental: each episode is processed once. A semantic summary can therefore be rebuilt or challenged against its source history.

## Temporal world model

The world model is a claim ledger, not an oracle.

Direct repository observations create claims such as repository.python_source_lines = 1532. Each claim cites the environment episode that supports it.

When an observed value changes, the prior claim is preserved as superseded and linked bidirectionally to the new current claim. This records change instead of silently rewriting history.

Confirmed or violated predictions and completed experiment outcomes also create claims with references to their prediction/experiment and reflection evidence.

## Cognition grounding

Current world claims may be supplied to the cognition boundary and cited by ID, but the claim itself retains links to raw evidence. Semantic memory is used for retrieval and context, not as unquestionable evidence.

## Trust ordering

1. Raw sensor observations and explicitly recorded experiment outcomes.
2. Derived world claims with source references.
3. Semantic memory used for retrieval.
4. Model-generated candidate thoughts.

Lower layers may guide attention but cannot overwrite higher-evidence layers.

## Still missing

- broader external perception;
- causal models richer than temporal claim revision;
- independent environmental action;
- self-authored code proposals;
- measured evidence that optional model cognition improves research outcomes;
- any evidence of subjective experience.
