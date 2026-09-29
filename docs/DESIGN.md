# Design: Genesis Phases 0–12

## Premise

AgentTest is an original experiment in persistent adaptive computation. It does not use a scalar alive score and does not treat fluent language or code volume as evidence of improvement.

## Adaptive loop

    human stimulus / auditable perception
                 ↓
        prediction scope check
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
        question → experiment → prediction
                 ↓
             next cycle

## Human interaction membrane

The interaction surface does not introduce a separate conversational agent.

A human message is recorded as the same kind of persistent stimulus evidence used by the core loop. The interaction wrapper then returns a view over the resulting state:

    human message
         ↓
    prior-memory retrieval
         ↓
    core adaptive cycle
         ↓
    source stimulus episode
         ↓
    interaction record
         ↓
    ┌──────────────┬───────────────┬────────────────┐
    │prior memory  │world claims   │self-model      │
    │retrieval aid │with evidence  │status/evidence │
    └──────────────┴───────────────┴────────────────┘
         ↓
    drives / intention / question / experiment
         ↓
    deterministic response rendering

The response text is not inserted into the world model as evidence. It is stored as an interaction artifact linked to the evidence that produced it.

## Interaction trust boundary

- The human input is a stimulus episode, not automatically a factual world claim.
- Semantic memory is retrieval context, not proof.
- World claims retain their own provenance.
- Self-model claims retain observed, verified, or unverified status.
- Model cognition, if available, remains a proposal and must pass its grounding boundary.
- If model cognition is unavailable, the deterministic loop continues and the response says so.
- A fluent reply does not imply subjective experience.

## Evolution evidence loop

    observed deficit
          ↓
    self-authored manifest
          ↓
    evidence-relevance review
          ↓
    verified read-only diagnostic when needed
          ↓
    ┌─────────────────────┬─────────────────────┐
    │no problem observed  │supported problem    │
    │close proposal       │candidate allowed    │
    └─────────────────────┴─────────────────────┘
                                  ↓
                         isolated candidate
                                  ↓
                    BASE-owned preservation gate
                                  ↓
                       live post-merge diagnostic

Historical failure evidence is preserved, but diagnostics are scoped to the repository baseline that produced them. A repaired baseline can therefore be re-tested and close an old problem without erasing the prior failure.

## Self-model discipline

Capability claims are explicitly calibrated:

- observed: citable runtime evidence exists;
- verified: reserved for stronger verified evidence;
- unverified: no adequate citable evidence exists, with a reason.

Explicit uncertainty counts as a grounded self-description. It does not count as evidence that the capability works.

## Open-endedness discipline

Raw question history is retained. A derived semantic family map groups near-equivalent inquiry. The open-endedness metric is based on family count rather than exact-string uniqueness. A protected diagnostic independently audits metric alignment.

## Trust ordering

1. Raw observations and explicit outcomes.
2. Verified diagnostics and provenance-backed world claims.
3. Semantic summaries used for retrieval.
4. Model-generated thoughts.
5. Interaction response text.
6. Change manifests and candidate code.

Lower-authority layers may guide attention but cannot rewrite higher-authority evidence.

## Still missing

- live successful model cognition, because no provider key is configured;
- graphical/web interaction surface;
- broader external perception/actions;
- causal models beyond current temporal/evidence structures;
- evidence of subjective experience.
