# World 2 native observation contract — design only

Status: proposal, not implemented or activated. Companion to `world2-causal-ecology-design.md` in draft PR #123. PR #4 is the coordination entry point; draft PR #124 owns the separate synthetic sensor pilot. Nothing in this document changes production code, state, authority, workflows or milestone gates.

Reviewed references: production `4509f6afece456ae4980fed22b27e37f26114303`; corrected proxy adapter `58c904c0b02c4a9bb7d0c302d0ee8b4cf5ab6cef`. The subsequent workflow-only replication must be assessed independently. Before implementation, re-read current code and handoffs rather than assuming these remain current heads.

## 1. What the corrected pilot establishes

The seed-1, 24-cycle matched pilot produced 11 prediction violations, 11 new repository-template questions and 18 foreground changes, versus none of these in its frozen control. Both arms had one initial admission invalidation and no later invalidations; neither had a genuine resumption. Evidence: isolated run `37215279840`, actual candidate/base checkout `90bc216c023b99f116dec907fa30998378a69313`.

This tests the unchanged core's response to changing numeric proxy channels. It does not show that Ora understands resources, objects, locations, delayed causes or native World 2 actions. The current adapter replaces visible-object identity with a count, maps resource readings onto `test_files`, maps slow signal onto `python_source_lines`, and collapses a missing resource channel and a measured zero to the same value. A new repository-template string is not a new semantic inquiry family. Actions in this pilot are externally scripted.

A native contract must remove those ambiguities before any claim of ecological learning. Repeating the proxy pilot across seeds is not a substitute for doing so.

## 2. Separate immutable configuration from observations

The host maintains an immutable experiment manifest containing exact code/schema/world versions, seed, initial state hashes, allowed action vocabulary, sensor schema and source-state provenance. Seed, latent-mode state, resource periods, pending-effect schedules and evaluator truth remain host-only.

Agent-facing configuration identifies the sensor/world contract with an opaque persisted instance/contract identifier. Do not derive that identifier from a small hidden seed space and treat the hash as a secrecy boundary. The host manifest supplies deterministic replay; the agent does not need the seed or hidden parameters.

A real contract/world-code change invalidates predictions made under the prior contract, with an explicit reason. Time advancement, movement, resource changes, object movement, delayed effects and latent environmental changes are data, not configuration interventions. Sensor values and sample clocks must never be folded into the configuration fingerprint.

Paired experimental arms share initial identity, admitted state, first observation, clock and permissions. Trial assignment labels and evaluator knowledge are not extra cognitive inputs.

## 3. Typed observable envelope

A future schema should carry these concepts without disguising them as repository statistics:

| Field | Meaning and scope |
| --- | --- |
| `schema_version`, `world_version`, `contract_id` | Fixed interpretation/instance identity; no hidden dynamics. |
| `observation_id`, `world_step` | Stable sample identity and world time; not a new baseline. |
| `position` | Measured agent position, using the existing coordinate convention. |
| `visible_object_ids` | Stable IDs observed at the current location, not remote object coordinates or attributes. |
| `local_resource` | Tagged measurement: measured integer 0–4, no channel at this location, or unavailable. These states are distinct. |
| `slow_signal` | Measured integer 0–9, explicitly tagged as a broadcast sensor in the current ecology. |
| `action_receipt` | Optional receipt for the single preceding permitted action, with actor before/after positions, blocked status and observed effect. |

The current ecology returns `None` when the agent stands at a location with no resource channel. That maps to `not_present_here`, not measured zero and not sensor failure. A future failed sensor maps to `unavailable`, not `not_present_here`. Absence of a channel here says nothing about remote locations.

An empty visible-object list means no objects were observed here. It does not imply that a previously observed object ceased to exist. A displaced object's new location remains unknown until observed; do not infer or disclose its destination using simulator internals.

The existing `slow_signal` is exposed at every position. Preserve and explicitly label that broadcast scope in a semantics-only adapter. Making it local would change the environment and needs separate design/versioning; do not silently claim that every existing sensor is local.

Example after a scripted interaction displaces the object at `[1, 0]` (illustrative IDs only):

```json
{
  "schema_version": "world2-observation-v1-proposed",
  "world_version": "causal-ecology-v0",
  "contract_id": "opaque-persisted-contract",
  "observation_id": "sample-000002",
  "world_step": 2,
  "position": [1, 0],
  "visible_object_ids": [],
  "local_resource": {"status": "not_present_here", "scope": "local"},
  "slow_signal": {"status": "measured", "value": 0, "scope": "broadcast"},
  "action_receipt": {
    "action": "interact",
    "before": [1, 0],
    "after": [1, 0],
    "blocked": false,
    "observed_effect": "object_displaced"
  }
}
```

The receipt describes the actor, not the object's destination. It exposes no latent mode or future slow-effect schedule. In the current simulator a receipt label such as `local_resource_changed` can occur at a saturated zero; the label alone must not be treated as proof of a nonzero measured delta.

## 4. Prediction and evidence semantics

Predictions identify a sensor/observable, its context (position or visible object identity where relevant), the contract, relevant time/action history and a later observable test condition. A resource reading at a different location is not automatically evidence that the original location changed. No-channel, unavailable and measured-zero outcomes cannot be interchanged.

Only observed outcomes can confirm or refute a prediction. An unobserved remote target is unevaluable, not false. Future labels and simulator truth are forbidden in agent-facing predictions, features and evidence. The host may retain them separately to evaluate a study, never to select Ora's actions or questions.

Preserve a trace from raw observation/receipt ID to prediction result, completed experiment, direct evidence reference, drive, intention, agenda decision and next-cycle reload. Source-family provenance remains different from evidence that directly advances a particular inquiry. Contract-intervention-invalidated records remain auditable history but earn no new-progress credit.

Question wording, numeric deltas and text diversity do not establish semantic learning. Claims of object persistence, temporal regularity or delayed causation need explicit supported predictions and held-out confirmations/refutations. A model must not appear to improve merely because evaluation targets became easier or were never observed.

Resumption accounting remains the existing stricter full-cycle causal contract: the same previously suspended thread must return because new direct evidence changes selection relative to the appropriate withheld-evidence counterfactual. Newly minted questions and ordinary returns to a default frontier are not replacement success criteria.

## 5. Experimental action boundary

The present pilot's script controls movement/interaction. Its provenance must remain explicit in reports, and cannot be relabeled as Ora's choices. A sensor-contract implementation does not grant an actuator or enable a planning lab.

A later native closed-loop experiment needs its own reviewed proposal: map one recorded selected action to one existing permitted internal-world action, persist the outcome, and show save/reload continuity. Do not run both the legacy action world and World 2 in the same cycle and accidentally double authority. No extra actions, filesystem/shell/network capabilities or external providers are authorized by this design.

The pure ecology stays independent of AgentCore and cannot write questions, priorities, thread evidence or milestone counters. A native consumer may require a separate observation/prediction extension because the current production consumer is repository-shaped. Do not solve that by silently renaming ecological measurements back into repository counters.

## 6. Acceptance gates before even isolated native claims

1. **Schema boundary:** deterministically serialize/reload; reject unsupported versions, malformed types, out-of-range measured values and unknown fields. Preserve unknown/unavailable status rather than filling it with zero.
2. **No truth leakage:** compare the actual agent-facing payload against an allowlist. Assert absence of seed, latent mode, remote resources/object positions, future effects and evaluator labels. Test records as well as the observation object.
3. **Configuration separation:** clock-only and ordinary observable changes preserve contract identity; real schema/world-contract changes invalidate old predictions. Replay is deterministic from the separate pinned manifest.
4. **Contextual measurements:** zero versus no channel versus unavailable, relocation between resource sites, visible-object absence/reappearance, object-ID continuity and broadcast scope all have positive and negative cases.
5. **Real consumer path:** use the actual proposed native consumer through prediction, direct evidence, drive, intention, selection, persistence and reload. Tests that inject a scored question or manufacture evidence downstream do not prove this path.
6. **Fair study:** fixed source, matched first admission/clock/budget, frozen and context-sensitive controls, all configured/effective seeds and phase classes reported, and a predeclared script or separately reviewed closed-loop policy. No acceptance condition requires World 2 to outperform control or pass Phase 42.
7. **Preservation:** unchanged legacy-world behavior, current unit/preservation/handoff/integrity/no-regression gates, no production state writes, no provider use and no extra action authority. Pin the exact tested code and state; retain trial-window reports and traces.

A failed gate identifies a contract or experiment problem to investigate. It is not permission to change scores, inject convenient observations, expose hidden rules or activate an external model.

## 7. Advancement and rollback

This document is design-only and does not authorize native implementation on main. First finish and interpret PR #124's corrected phase-configuration replication. Then select one bounded isolated native-contract implementation with explicit production-consumer changes, if needed, reviewed separately from environment changes or autonomous action wiring.

No simulation result promotes the production organism. Autonomous activation requires a separate checkpoint, reviewed opt-in wiring, full integration and post-change natural verification. Phase 42/43 scientific gates remain independent of environmental acceptance. Roll back an experimental adapter without rewinding live history or replacing the preserved production baseline.
