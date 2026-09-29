# Design: Genesis Phases 0–3

## Premise

AgentTest is not an imported agent framework. It is an experiment in building measurable organism-like computational properties from simple, inspectable mechanisms.

There is deliberately no scalar "alive score."

## Current loop

    repository perception
           ↓
    compare with prior prediction ─────→ prediction error
           ↓                              ↓
    persistent memory                  internal drives
           ↓                              ↓
    environmental surprise ─────────→ chosen intention
                                          ↓
                             optional cognition boundary
                                          ↓
                        validated candidate thought or reject
                                          ↓
                                  generated question
                                          ↓
                               falsifiable experiment
                                          ↓
                               next-state prediction
                                          ↓
                                  next heartbeat

## Generative cognition is advisory

The model is not the organism's source of truth. It receives a compact evidence catalog and may propose exactly one structured candidate containing a question, hypothesis, experiment, falsifier, predicted observation, evidence IDs, confidence, and a novelty note.

The provider receives no tools. It cannot edit state, metrics, files, evidence, or code.

Every returned evidence ID is checked against IDs already present in persistent state. Unknown references reject the entire candidate. If no provider is configured or the provider fails, the deterministic evidence loop continues.

A validated candidate may influence the next question and proposed experiment, but it remains a proposal until later evidence resolves it.

## Provider boundary

The first optional provider uses OpenAI's Responses API with Structured Outputs and no tools. It is enabled only when OPENAI_API_KEY exists. The default model is gpt-6-luna; AGENTTEST_MODEL may override it.

Provider absence is not an error and cannot halt the heartbeat.

## State migration

The repository baseline state file is no longer rewritten merely to add schema fields. StateStore.load() migrates older state additively and save() persists the upgraded form. This prevents capability upgrades on main from overwriting accumulated experience on autonomous/growth.

## Drives are not emotions

Drive values are numerical control pressures, not claims of subjective feeling.

## Anti-busywork rule

When evidence hunger is dominant, the loop selects an existing unresolved experiment instead of creating another one.

## Still missing

- semantic long-term memory;
- a richer causal/world model;
- broad environmental perception;
- independent environmental action;
- self-authored code proposals;
- evidence that model-generated thoughts improve outcomes rather than merely add variety;
- any evidence of subjective experience.
