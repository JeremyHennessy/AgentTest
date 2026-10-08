# Ora 2 — local exception memory prototype (not admitted)

This isolated predictor is a narrow follow-up to the previously registered action-effect transfer result (PR #255, run 37818768173). That result passed its own **retrospective spatial-holdout** screen (25/25 positive location folds and 7.110874724691012 bits/case advantage over a weak non-spatial baseline). It did **not** test self-guided exploration or general-world transfer. The exact 95-case archived report includes one missed action outcome that a location-independent rule could not predict, despite explaining 94/95 other held-out cases.

## Hypothesis, kept separate from proof

Ora may need to retain both broad regularities and local counterevidence: learning a useful action effect from many places need not entail believing it is exceptionless everywhere. This model uses only recorded before/action/after transitions and their distinct source IDs; it never reads the world's hidden rule maps. There are no hardcoded obstacle locations, action-direction mappings or authored solutions.

The immutable source history remains the persistence layer. No new state writer, cache, history purge or serialized mutable belief object is introduced; reconstructing from the same preserved records yields the same forecast. A global action-effect distribution (from the earlier isolated research module) is mixed with a local empirical successor distribution. The local weight is `observations/(observations+2)` and both distributions use the previously declared 90/10 empirical/uniform smoothing. **Both mixture shape and weighting are engineer-authored; they are not learned meta-control.**

A pre-action diagnostic records whether local evidence disagrees with the general pattern, how much evidence supports it and which source IDs were used. No choice or actuation is authorized from that diagnostic. It cannot infer an unobserved exception, justify interrupting an inherited goal, or decide whether to experiment. Contradictory/noisy evidence retains uncertainty, but the prototype currently assumes a fixed world; concept drift and noisy outcomes would require separate tests.

## Acceptance boundary

This PR may be merged into Ora 2's development branch only as a **default-off software research capability** after exact-head CI, full diff review and no-regression verification. Synthetic tests check (1) unseen-context transfer, (2) adaptation after actual counterevidence, (3) repeated exception consolidation, (4) local evidence isolation, (5) contradictory effects, (6) cold reconstruction, (7) opaque action labels, and (8) world/provenance rejection. They are not a comparative scientific benefit screen.

**Not authorized by this step:** editing original Ora or its Observer, enabling a persistent Ora 2 pilot, changing the Core lifecycle's action owner, treating authored exceptions as discovered, importing old Phase 42 machinery or using any model API. Do not reuse Timing Study 001's negative result to claim a win.

## Mandatory next study design

Before any live use, predeclare and then test an independent online/counterfactual comparison in richer **isolated copied environments**, where world-local effects or obstacles genuinely vary, the learner sees only public observations and its own observed consequences, and hidden dynamics are unavailable to the learner. Evaluate the unchanged learned component against a stronger appropriately spatial comparator, not only the weak absolute-location baseline. Hold out whole worlds/contexts, preserve event-source identity, verify cold replay, measure prediction calibration, safe action attribution and original inherited-goal continuity separately. No hand-authored solution sequences or hidden answer labels may be passed to Ora; the richer world remains inactive until its separate evidence gate.
