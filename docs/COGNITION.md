# Cognition Boundary

Phase 3 adds optional model-backed generative cognition without turning a language model into the authority over AgentTest.

## Contract

One cognition call may return one candidate thought with these fields:

- question
- hypothesis
- experiment
- falsification
- predicted_observation
- evidence_refs
- confidence
- novelty_note

The provider has no tools. The request contains only a compact state summary and a bounded evidence catalog.

## Validation

A candidate is accepted only if every required field is present, confidence is between 0 and 1, and every evidence reference exists in persistent state.

Accepted means structurally admissible, not true.

Accepted candidates remain status=proposed. Later observations or explicit experiment outcomes must supply evidence.

## Failure behavior

If no provider is configured, cognition is recorded as unavailable and the deterministic loop continues. Provider/network errors are recorded and likewise cannot halt the heartbeat.

## OpenAI provider

The optional built-in provider calls the Responses API with Structured Outputs and no tools. It reads OPENAI_API_KEY and optionally AGENTTEST_MODEL from the environment. The default model is gpt-6-luna.

The response ID, model, usage metadata, prompt version, and a hash of the exact supplied cognition context are preserved with each cognition event for provenance.

## Evaluation question

The presence of a model is not itself an improvement. Phase 3 succeeds only if model-backed candidates later demonstrate better novelty, falsifiability, resolution rate, or information gain than the deterministic baseline without increasing unsupported claims.
