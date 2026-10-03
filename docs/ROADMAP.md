# Research Roadmap

This roadmap is hypothesis-driven and evidence-gated. It is a custodian planning document, not a runtime instruction surface: Ora does not read this file to choose actions.

A phase advances only when its predecessor produces reproducible evidence. Live behavior may change the ordering, scope, or necessity of future phases.

## Phases 0–14 — verified foundations

- **Phase 0:** persistent growth substrate.
- **Phase 1:** auditable self-perception.
- **Phase 2:** predictive drives and endogenous intention.
- **Phase 3:** grounded generative cognition boundary.
- **Phase 4:** semantic memory and temporal world model.
- **Phase 5:** behavioral preservation gate for future self-modification.
- **Phase 6:** evidence-backed self-authored change proposals.
- **Phase 7:** evidence relevance review for self-authored proposals.
- **Phase 8:** verified non-mutating evidence diagnostics.
- **Phase 9:** intervention-aware prediction scope.
- **Phase 10:** verified self-model grounding diagnostic.
- **Phase 11:** verified inquiry-family diagnostic.
- **Phase 12:** persistent evidence-linked human interaction.
- **Phase 13:** owner-authorized GitHub interaction channel.
- **Phase 14:** evidence-debt-aware evolution governor.

These phases established the persistent state, evidence hierarchy, governance, interaction membrane, and preservation gates required for later autonomous work.

## Phases 15–31 — experiment and attention governance

- **Phase 15:** evidence-ready experiment lifecycle.
- **Phase 16:** verified intervention reconciliation.
- **Phase 17:** readiness-aware learning governance.
- **Phase 18:** protected experiment-design diagnostic.
- **Phase 19:** stop duplicate experiment proliferation.
- **Phase 20:** specification debt as a first-class drive.
- **Phase 21:** protected system diagnostics as self-change evidence.
- **Phase 22:** experiment-specification triage.
- **Phase 23:** protected blocked-attention diagnostic.
- **Phase 24:** blocked-attention diagnostics as self-change evidence.
- **Phase 25:** blocked-attention redirection.
- **Phase 26:** executable prediction experiments.
- **Phase 27:** opt-in grounded experiment admission.
- **Phase 28:** park blocked experiment debt.
- **Phase 29:** keep autonomous attention off parked inquiry.
- **Phase 30:** let empirical outcomes change future predictions.
- **Phase 31:** transfer mature empirical evidence into attention and create evidence-linked frontier inquiry.

This sequence moved Ora from accumulating experimental debt toward distinguishing evidence-ready work, blocked work, repeated work, and empirically useful attention.

## Phase 32 — bounded persistent causal action lab — verified

Ora gained explicit bounded action authority inside the internal micro-world.

The action lab:

- persists action history;
- learns transition effects from experience;
- fails closed on corrupted history;
- avoids immediate blocked-state retry loops;
- exposes no hidden transition map to planning code;
- allows one bounded internal action per authorized heartbeat.

## Phase 33 — persistent goal-directed planning — verified

Ora can form a multi-step goal, persist its plan across heartbeats, execute one step per cycle, and detect completion.

## Phase 34 — state-dependent model revision — verified

Ora can detect when a learned general effect fails in a particular state, preserve the surprise as evidence, and replan around the newly learned exception.

## Phase 35 — evidence-valued curiosity — verified

After a relevant model surprise, Ora may spend a bounded action to gather information when the expected information value exceeds the delay cost to the current goal.

## Phase 36 — episodic memory changes route choice — verified

Completed routes become citable episodic memories. Prior route experience can change a later equal-cost route choice, with the counterfactual route retained for inspection.

## Phase 37 — bounded transfer — verified

Ora distinguishes general action effects from world- or state-specific exceptions and can probe whether prior knowledge transfers into a new bounded context.

## Phase 38 — self-generated falsifiable bounded experiments — verified

Ora can generate a bounded hypothesis, prestate a falsification condition, execute the experiment, and preserve whether the hypothesis was supported or refuted.

## Phase 39 — bounded self-selected objectives — verified

Ora can select among reachable objectives using her own evidence-valued criteria rather than always accepting the default least-visited/farthest target.

A Phase 39 decision must preserve:

- the selected objective;
- the counterfactual objective;
- the decision margin;
- evidence references that made the choice possible;
- whether the self-selected objective actually changed the choice.

## Phase 40 — precommit and realize objective information — live and verified

Phase 40 closes the gap between an objective being *predicted to be informative* and the organism actually measuring whether information was obtained.

For an eligible completed self-selected objective, Ora can:

1. identify one unresolved local action;
2. persist a hypothesis and falsification criterion **before acting**;
3. execute the precommitted action on a later heartbeat;
4. compare prediction with observation;
5. record local sample count before and after;
6. record realized information gain;
7. classify the hypothesis as supported or refuted;
8. return to normal objective pursuit.

### First natural live realizations

As of 2026-10-01, the autonomous growth branch has produced two independent complete Phase 40 sequences.

**OR000001 → OI000001**

- objective: PG000201;
- state: `[-1, -2]`;
- precommitted action: east;
- predicted result: `[-1, -3]`;
- observed result: blocked, position unchanged;
- interpretation: hypothesis refuted;
- local samples: 0 → 1;
- realized information gain: 1.0.

**OR000002 → OI000002**

- objective: PG000204;
- state: `[2, -1]`;
- precommitted action: north;
- predicted result: `[3, -1]`;
- observed result: blocked, position unchanged;
- interpretation: hypothesis refuted;
- local samples: 0 → 1;
- realized information gain: 1.0.

These are distinct states and actions. After each realization, Ora resumed ordinary goal pursuit rather than looping on the experiment.

### Phase 40 integration sanity gate

A dedicated cross-phase verification gate now checks the class of failure discovered during Phase 40 rollout: if Phase 39 values unresolved boundary information, Phase 40 must be able to form a reachable precommit for that information.

This is a verification-only contract. It does not alter Ora's planning policy or runtime behavior.

## Phase 41 — outcome-aware objective valuation — verified

**Research question:** can the *measured outcome* of previous objectives change which objective Ora selects later?

Phase 41 is verified at immutable checkpoint `checkpoint/2026-10-02-phase41-success` → `76cc1f73fae48c774070d7a166abfdfbe9260083`.

### Natural promotion evidence

At cycle 1768, decision `OD000081` preserved the Phase 39 counterfactual target `[-1, -2]` with score `0.640385`, while persisted Phase 40 outcome evidence changed the selected objective to `[2, 2]` with outcome-adjusted score `0.92724` and outcome margin `0.286855`.

The decision cited persisted outcome evidence `OI000002`, `OI000007`, `OI000011`, and `OI000012`. Episodic memory then changed the route, and cycle 1771 completed `PG000440` at `[2, 2]`.

This is the promotion evidence: measured prior objective outcomes changed a later objective choice while preserving the counterfactual choice and evidence references. The checkpoint is historical and must not be treated as the current production head.

## Phase 42 — persistent multi-thread internal agenda — implemented, natural gate pending

**Research question:** can Ora maintain several worthwhile investigations over time rather than living entirely one objective at a time?

The pre-Phase-42 immutable reference is `checkpoint/2026-10-02-pre-phase42` → `6493c20940b4d1cadf9887b76c4a9ad73d149331`.

The live implementation maintains a bounded persistent agenda over existing questions. It preserves:

- at most four live inquiry threads;
- foreground and suspended state;
- suspension reason and resume condition;
- bounded decision history;
- explicit counterfactual and evidence references;
- one-action bounded internal-world authority.

Subsequent stabilization work tightened the production contract:

- source-family provenance remains auditable but does not count as fresh thread-progress evidence;
- only actually proposed linked experiment work counts as an active experiment path at agenda-scoring time;
- the autonomous growth workflow runs a Phase 42 live-state integrity check and a read-only resumption-opportunity diagnostic;
- normal growth and human-interaction workflows do not invoke external model-provider cognition.

These are implementation and reachability safeguards, not Phase 42 promotion evidence.

### Natural promotion gate

Phase 42 remains **unpassed** until fresh natural persisted behavior demonstrates all of the following:

- multiple competing inquiry threads;
- a genuine foreground → suspended transition;
- later resumption of that **same** prior thread;
- a priority change causally supported by newly persisted thread-progress evidence;
- no starvation loop in which one thread permanently monopolizes attention;
- preserved counterfactual and evidence references;
- unchanged one-action authority.

Initial thread creation is not resumption. Synthetic, deterministic, cross-capability, or manually induced tests can prove mechanism reachability but do not satisfy the natural capability gate.

The current read-only opportunity diagnostic is intentionally descriptive: a lack of qualifying resumption opportunities is not itself evidence of a runtime defect and must not be “fixed” by score tuning, timers, round-robin scheduling, hard-coded question IDs, or invented evidence.

## Later horizon — endogenous cognitive tempo

Do **not** implement this merely as staggered wall-clock schedules.

The later research direction is to separate logical modes such as:

`observe → deliberate → precommit → act → observe result → revise`

The eventual question is whether Ora can use her agenda, uncertainty, expected value, and evidence state to decide whether the next authorized cycle should primarily deliberate, test, move, investigate, or refrain from acting.

A familiar situation might justify immediate action. A novel or high-uncertainty situation might justify additional deliberation first.

This direction should not be promoted until Phase 41 and Phase 42 provide meaningful evidence on which such mode selection could operate.

## Custodian rules for future phases

- Do not promote a phase because code was written; require live or deterministic evidence that the capability is reachable.
- Add cross-capability handoff sanity checks when a new phase consumes the output of a previous phase.
- Prefer minimal, reversible changes.
- Preserve behavioral and governance boundaries unless the phase explicitly requires changing them.
- Keep Observer/UI work descriptive; it must not become hidden cognitive input.
- Record counterfactuals wherever a claim depends on a choice actually changing.
- Do not infer consciousness, sentience, or subjective experience from behavioral milestones.
- If live behavior contradicts this roadmap, revise the roadmap before forcing the organism to fit it.
