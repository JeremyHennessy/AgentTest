# World 2 — Causal Ecology Design

Status: design only; not wired into AgentCore, state migration, growth workflow, or autonomous authority.

Baseline: main@4509f6afece456ae4980fed22b27e37f26114303

## Purpose

Increase environmental richness without changing Ora's inquiry, scoring, planning, evidence, or action-authority rules. The environment should create multiple persistent phenomena whose evidence can become relevant while an inquiry is unattended. It must not be designed to manufacture a Phase 42 resumption or a Phase 43 milestone.

## Preservation constraints

- Existing bounded, stateful, and transfer worlds remain byte-for-byte behaviorally compatible.
- World 2 is a new explicit world version and is opt-in during isolated tests.
- No OpenAI API or external model/provider dependency.
- No network, filesystem, shell, subprocess, or external side effects from world dynamics.
- Hidden dynamics are inaccessible to the organism except through whitelisted observations and action outcomes.
- Existing action vocabulary remains valid initially; richer actions require a separate authority review.
- World 2 cannot directly alter agenda scores, questions, experiments, or milestone counters.
- Deterministic replay from seed + prior world state + action + cycle must reproduce every outcome.
- A preserved simple-world checkpoint is required before autonomous activation.

## State model

World 2 extends location with independent persistent state:

1. **Objects**
   - stable identities
   - locations
   - observable attributes
   - hidden attributes that affect outcomes only through interaction

2. **Resources**
   - bounded scalar quantities
   - local or global
   - replenishment/depletion rules
   - effects visible only through observations or action consequences

3. **Processes**
   - deterministic processes that advance even when not directly attended
   - different periods/timescales
   - process state persists across cycles

4. **Conditions**
   - latent environmental modes
   - change transition behavior, object behavior, or process rates
   - inferred from consequences rather than exposed as labels

5. **Events**
   - deterministic seed-derived rare transitions
   - not announced before they occur
   - recorded after observable consequences only

## Initial ecology

The first isolated implementation should contain at least four independent phenomena.

### A. Periodic resource field

A resource at several locations changes on a period independent of Ora's visits. Different locations use different phases. Sampling the same location at different times can therefore produce different observations.

Research value: temporal prediction, delayed revisitation, distinguishing location effects from time effects.

### B. Persistent movable object

One object can be displaced by a normal interaction and remains at its new location. Its presence changes one locally observable outcome but does not block movement.

Research value: object permanence, causal intervention, memory across absence.

### C. Latent condition

A hidden two-state condition changes only after a deterministic combination of world state and cycle. It changes the effect of one otherwise familiar interaction.

Research value: model revision, competing causal explanations, surprise without random noise.

### D. Coupled slow process

A slow variable changes as a delayed consequence of resource state or object position. The effect becomes observable several cycles after the cause and can continue while Ora investigates something else.

Research value: delayed causality, cross-thread evidence, natural reasons to resume old inquiries.

## Non-goals

World 2 must not:

- assign explicit rewards for discovering hidden rules;
- name hidden rules in observations;
- create a special "resumption event";
- boost suspended-thread priority;
- inject questions directly into the agenda;
- guarantee that any inquiry resumes;
- require Ora to discover every phenomenon;
- use stochastic noise to fake novelty;
- enlarge the world merely for map size.

## Observation contract

An observation exposes only values a bounded sensor could legitimately measure at the current state, for example:

- current position;
- visible object IDs at current position;
- local resource reading;
- outcome of the chosen interaction;
- coarse observable condition effects, never the hidden condition label;
- timestamps/cycle numbers already available to Ora.

Unobserved remote state is not exposed.

## Determinism and replay

World state transition is a pure function:

    next_world = transition(previous_world, action, cycle, seed)

Observation is separately derived:

    observation = observe(next_world, position, last_action)

Tests must prove:

- identical seed/state/action/cycle => identical transition and observation;
- replay reconstructs persisted history;
- hidden configuration never appears in observations;
- no external imports/effects;
- old worlds remain unchanged.

## Evaluation plan before autonomous use

1. Implement as an isolated module with no AgentCore wiring.
2. Run deterministic simulations across many seeds/cycle horizons.
3. Verify at least four phenomena are observable in principle but not trivially exposed.
4. Verify phenomena can generate evidence on different timescales.
5. Verify no single scripted path is required to encounter all phenomena.
6. Build a test harness using a simple non-Ora explorer to measure reachability only.
7. Run existing AgentTest suite unchanged.
8. Only then consider an opt-in local Ora simulation.
9. Compare simple-world and World 2 behavior from the preserved baseline.
10. Autonomous activation requires a separate reviewed PR and explicit evidence that the environment broadens observations without changing cognition/agenda authority.

## Success criteria

World 2 is successful if it creates a richer evidence ecology, not if Ora passes a phase.

Evidence of environmental success would include:

- multiple distinct observable phenomena encountered;
- questions/evidence distributed across more than one phenomenon;
- delayed evidence can arrive after attention moved elsewhere;
- learned models can be confirmed and refuted;
- some regularities remain undiscovered for meaningful periods;
- repeated runs from the same seed are exactly reproducible;
- no existing capability or simple-world behavior regresses.

A genuine Phase 42 resumption occurring in World 2 would be an observation, not a World 2 acceptance criterion.
