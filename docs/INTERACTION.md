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

Live GitHub interaction uses the deterministic evidence loop only; it does not call an external model or require an API key.

## GitHub-native channel

After Phase 13 is enabled, the repository owner can use either surface:

### Issue / pull-request comment

```text
/agent What are you investigating now?
```

Only comments authored by the repository owner are accepted. The response is posted back to the same issue or pull request after the interaction state passes verification.

### Actions workflow

Open **Actions → Human Interaction → Run workflow**, enter a message, and optionally enable configured model cognition.

Both paths use the same persistent `autonomous/growth` state and the same `agenttest interact` implementation. They are transports, not separate agents.

The interaction workflow shares the autonomous-growth concurrency group, so a human turn and a scheduled heartbeat cannot write the persistent branch simultaneously.

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
