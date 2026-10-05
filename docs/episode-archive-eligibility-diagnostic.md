# Conservative episode archive eligibility diagnostic

Status: diagnostic only. No production retention, pruning, tombstones, archive lookup, or compaction.

Production base: `e3672c473723159232ab494a108eeca7d1903842`.

Pinned copied state: `autonomous/growth@906d216b54d76e3cb57c540cf59fd57004f29bf3`, cycle 4348.

## Question

After monotonic episode identity, semantic sequence consolidation, and native inquiry sequence freshness are deployed, can a **conservatively protected** set of old episodes be removed from a disposable state copy without changing ordinary autonomous behavior over a bounded replay?

This is not the same as asking whether every externally unreferenced episode is safe to delete.

## Protection rules

An episode is ineligible for the diagnostic archive if any of these applies:

1. its exact ID appears anywhere outside the episode ledger in current state;
2. it is inside a 1,024-episode hot suffix;
3. it is needed to build a pending Planning Lab episodic-route memory;
4. it is an environment episode needed for a world-model snapshot not yet consolidated;
5. it belongs to the current or immediately prior organism cycle;
6. its ID is opaque/non-numeric rather than a normal Core `E...` sequence.

The diagnostic fails closed if current state already contains a missing externally referenced episode ID.

## Replay protocol

From the immutable pinned state:

- derive the protected and eligible sets;
- choose the oldest 1,000 eligible episodes;
- serialize those exact records to a gzip diagnostic artifact;
- create untouched and pruned disposable state copies;
- run five ordinary Core cycles in separate fresh Python processes with:
  - identical stable repository observations,
  - `strict_experiment_admission=True`,
  - `planning_lab=True`,
  - controlled equal timestamps,
  - cognition disabled;
- compare each resulting cycle.

The baseline is normalized only by filtering the exact selected archive IDs and by setting legacy semantic `last_episode_index` to the retained list length. `last_episode_sequence`, all substantive semantic memory, allocator state, agenda, labs, world model, Phase42-related state, and every other field must remain equal.

Expected comparisons each cycle:

- complete normalized state;
- complete Core result;
- episode sequence after applying the same archive filter;
- generic evidence universe after subtracting only the intentionally archived episode IDs.

The diagnostic also asserts that ordinary cycles do not create new external references to any selected archived ID.

## Why generic evidence authority is still a blocker

Even if the replay matches, archived episode IDs disappear from current `known_evidence_ids()` because no archive authority/lookup exists yet. That is intentional in this diagnostic.

Therefore a successful result would establish only that the **tested old records are behaviorally cold over the bounded ordinary replay** under the conservative policy. It would not establish a production archive contract.

The next implementation boundary would still need to define whether archived evidence:

- remains admissible evidence by ID;
- is loadable on demand;
- is excluded from generic authority but available to specific historical consumers;
- has cryptographic/manifest integrity;
- participates in native inquiry grounding/resolution;
- is included in self-model/cognition/review surfaces.

## Explicit non-scope

This branch must not:

- modify `src/agenttest/**`;
- delete production data;
- add archive or tombstone fields to live state;
- broaden `known_evidence_ids`;
- change StateStore layout;
- change journal rollover;
- change Phase42 scoring/credit;
- change agenda capacity/priorities;
- change Action Lab, Planning Lab, world mechanics, or environmental authority;
- enable any external/OpenAI model provider;
- alter Observer/UI.

The separate `fix/state-storage-blob-guard@970e1fd54e70b457069ec075e6086e0798adfd22` remains independent.

## Interpretation discipline

A pass means only:

> On the pinned state, removing the oldest 1,000 episodes that are neither explicitly referenced nor protected by the listed raw-consumer rules produced the same five-cycle ordinary behavior after expected archive normalization.

A fail is equally useful: it identifies an unmodeled raw consumer or reference contract and must be investigated before any production retention implementation.
