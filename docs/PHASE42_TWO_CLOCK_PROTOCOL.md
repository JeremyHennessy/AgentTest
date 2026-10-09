# Phase 42 two-clock memory — controlled changed-environment protocol

**Frozen design before execution, October 9, 2026.** AgentTest research only. AI-Research is read-only. Original Ora history, heartbeat and approved UI remain untouched. Built on the original-world spatial evidence predictor in PR #265, but new source, model ID, physical test, sample counts and score thresholds must be independent. The retrospective 7319-action result cannot be reused as a new independent test.

## The physical question

Can a memory controller retain a stable long-term model while **selectively** revising one local belief after repeated contrary observations, rather than either remaining stuck in the past or discarding all acquired experience?

Scientific inspiration: AI-Research Passes 12–16 distinguish within-life material memory, costs of readiness, latent switching and genuine prediction from mere state persistence. These papers motivate *tests*, not an installed consciousness or biological-equivalence claim. A positive software test in an authored world is not alive or generally intelligent.

## Full fixed physical panel (all outcomes and failures)

This is a deliberately externally driven **model-identification experiment**, not autonomous organism behavior. The physics harness can query a canonical original 5×5 world or its existing transfer-world variant. It evaluates **every** legal position (x and y from -2 through +2) against **every** one of the four movement actions, exactly once per sweep: 25 × 4 = 100 physical probes. All probes are independent, reset-to-state calls; do not interpret them as a single individual traversing 100 states.

Exactly **six** complete training sweeps (600 observations) are supplied before the test without revealing future intervention labels to the models. Exactly **four** further complete sweeps (400 probes) are scored one observation at a time, with every model predicting before receiving the actual result. All models receive the same public position/action and past reported outcomes; no hidden world version, barrier map, physics code or answer is supplied to prediction. The private experiment adapter retains exact physical versions and change boundaries as **provenance only**.

Four fixed scenario panels, independently initialized:
1. Original stateful → original stateful (**no-change control**).
2. Original stateful → transfer variant (**forward change**).
3. Transfer variant → original stateful (**reverse change**).
4. Original stateful → original stateful, except **one explicitly simulated faulty sensor observation**, at the first evaluation sweep, public position (0,2) and action south. The simulator's true observed after-state is scored; only the model's post-action *training input* is replaced with a different supported one-cell-or-still reading. Label this as injected telemetry error, never a real original-world event.

Order in every sweep: x ascending, then y ascending, then public action order north/east/south/west. All experiments use the same complete coverage and fixed stopping rules; no seed search, favorable trajectory, engineered puzzle reward, resource rescue or world state from the original growth branch.

## Frozen prediction grammar and policies

Possible public displacement observations: (0,0), (+1,0), (-1,0), (0,+1), (0,-1). Other effects fail validation. All probabilities remain positive and normalized.

- **LIFETIME-1:** general action Dirichlet(0.5 each) prior; local position/action likelihood with weight n_local/(n_local+3) against that prior. Uses every past event. No forgetting or switch labels.
- **TWOCLOCK-1:** identical lifetime model unless an entirely *observed* local change gate fires: at least four preceding local observations, prior dominant outcome ≥80% of the pre-last-two local events, and the last **two** observations agree with each other but disagree with the earlier dominant. After that gate, short-time local evidence begins at the first of the two contradictory rows, mixed with the same action-general prior at pseudo-count 1.5. Earlier rows remain fully preserved for replay, evidence lineage and other contexts. No automatic global forgetting, changed-world oracle, label-based routing or decision reward.
- **ACTION-1:** general action Dirichlet only, no location.
- **UNIFORM-1:** no memory, five equal probabilities.

A local change marker can be activated by historical observations only **after** they occur, never retroactively inserted into a prior forecast. The model has no direct access to which scenario is running. A single noisy contradictory row must not meet the two-row change gate. Every stored row is immutable; retaining a short active view is not deleting earlier evidence.

## Score contract

At each of 400 evaluation probes, freeze the four predictions, score multiclass Brier and log loss against **true simulation result**, record source position/action, then append that outcome to each arm's memory. Only the noise comparator appends the declared one corrupted sensor report; it scores against true observation and records both values. A cold-process/reconstructed model must match next forecasts exactly.

The evaluator independently identifies **changed position/action pairs** by comparing both physical laws across the complete 100-pair panel *before running models*; this set is used only for reporting, never exposed to learner code. Expect two changed pairs from current source; if the laws do not match the frozen differential, stop rather than redefine "changed" after seeing results. Report separately:
- all 400 evaluation probes;
- all affected pairs (2 × 4 = 8 probes) and unaffected pairs (98 × 4 = 392);
- affected *late* probes (sweeps 3–4, four observations) after at least two chance observations;
- number/timing of genuinely observation-triggered local markers;
- false change markers in no-change and single-noise scenarios;
- log loss/Brier, prediction costs, all nulls, invalids and source hashes.

**Descriptive pass threshold:** In BOTH forward and reverse change panels, TWOCLOCK late-affected mean Brier is strictly below LIFETIME, with **zero** false markers in no-change and noise panels and unchanged-event performance no worse by more than 0.01 absolute Brier. Any other result is negative/mixed. Do not tune these constants or adjust evaluation chronology after seeing outcomes.

## Custody and limits

All data is deliberately synthetic/known authored physics, so there is no natural-world replication, endogenous intervention or independently evolving individual. The test cannot claim useful natural Ora decision-making, new environmental function, organism/lineage reproduction or consciousness. It can establish or refute only specified history-dependent *prediction*. No host network/API, Github state writes, persistence cutover, scheduled world actuation, autonomous new-world activation or Observer changes. A later live integration requires separate no-regression checks, authenticated native evidence, and protection of Ora's active commitments.
