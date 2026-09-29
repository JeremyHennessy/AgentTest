# Interaction Membrane

Phase 12 adds a persistent human interaction surface without creating a second chatbot personality.

## Command

```bash
PYTHONPATH=src python -m agenttest interact "What are you investigating?"
```

Optional flags:

```bash
PYTHONPATH=src python -m agenttest interact \
  --self-observe \
  --cognition \
  "What changed since the last cycle?"
```

`--cognition` only uses a configured provider. If no provider is available, the interaction remains fully functional through the deterministic evidence loop.

## What a turn does

1. Load the persistent state.
2. Retrieve semantic memory relevant to the message **before** writing the new turn.
3. Run one normal AgentTest cycle with the message as stimulus.
4. Mark the source episode as a human interaction.
5. Persist an interaction record linked to:
   - source episode;
   - selected intention;
   - generated question;
   - current experiment;
   - cognition event/candidate when present.
6. Recalibrate the interaction capability from the actual source episode.
7. Return a structured view of prior memory, prior world claims, self-model status, current adaptive state, and a deterministic text rendering.

## Evidence levels

The interface keeps these categories separate:

- **Human stimulus:** something the user said; not automatically a world fact.
- **Semantic memory:** retrieval context derived from past episodes.
- **World claim:** provenance-backed derived claim.
- **Self-model claim:** observed, verified, or explicitly unverified.
- **Question/experiment:** unresolved proposal.
- **Model candidate:** optional proposal that passed structural grounding, not fact.
- **Response text:** a rendering of state; never promoted to evidence merely because it sounds fluent.

## Why no persona layer yet

A conventional chatbot persona would make AgentTest feel more alive without necessarily increasing persistence, calibration, learning, or evidence-grounded agency.

Phase 12 therefore exposes the state directly first. A richer conversational presentation can be added later without changing the evidence hierarchy underneath it.
