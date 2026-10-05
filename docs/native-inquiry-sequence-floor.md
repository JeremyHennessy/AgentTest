# Native inquiry freshness by monotonic episode sequence

Status: bounded retention prerequisite; no archive/pruning activation.

Production base: `404ea4be0127d14fe419e635b239c2e51e9c4532` (PR #182 merged).

## Problem already established

PR #181 proved that the native temporal resolver still uses a positional freshness contract:

- inquiry creation stores `resolution_evidence_floor_episode_count = len(episodes)`;
- resolution finds the outcome's **current list index**;
- an outcome is rejected when that current index is below the stored count floor.

After unrelated prefix archival, a genuinely later outcome can shift to a lower list index and be incorrectly rejected as predating the inquiry.

PR #182 fixed the independent semantic-memory positional cursor. This document addresses only the native inquiry freshness contract.

## Candidate contract

Newly staged native inquiries retain the legacy count field for compatibility/observability and additionally store:

`resolution_evidence_floor_episode_sequence`

The sequence floor is `next_episode_index - 1` at inquiry creation. New Core native evidence is allocated from the monotonic episode sequence introduced by PR #180, so:

- grounding/pre-inquiry evidence has sequence <= floor;
- a newly recorded post-inquiry outcome has sequence > floor;
- unrelated removal of earlier list entries does not alter that ordering.

The resolver prefers the sequence floor whenever it exists and requires the referenced native outcome episode to have a numeric Core episode sequence.

## Legacy inquiries

An existing inquiry that has only the old count floor keeps the old positional check **only while the ledger remains dense**.

If the saved episode watermark shows that the retained ledger has already lost records (`next_episode_index != len(episodes) + 1`), a legacy count-only inquiry fails closed instead of guessing freshness from a shifted list.

This is intentional. The candidate does not rewrite historical inquiry metadata or invent a sequence floor after archival.

## Explicit non-scope

This change does not:

- delete, archive, compact, or tombstone episodes;
- add an archive loader;
- change `known_evidence_ids`;
- change evidence authority;
- make missing archived evidence discoverable;
- change semantic-memory cursor behavior;
- change Phase 42 scoring or credit;
- change agenda limits/priorities;
- grant Action Lab, Planning Lab, or environmental authority;
- activate the richer-world source;
- enable any external/OpenAI model provider.

Grounding/outcome evidence still must be present in the episode ledger when the resolver reads it. Future archive work must preserve or deliberately expose every evidence record needed by active inquiries.

## Verification

Focused resolver tests cover:

1. new inquiries record both legacy count and monotonic sequence floors;
2. a sequence floor remains sufficient if legacy count metadata is absent;
3. a genuinely fresh post-inquiry outcome resolves after unrelated prefix removal;
4. a matching outcome recorded before inquiry creation remains stale after the same removal;
5. a legacy count-only inquiry remains compatible while no removal occurred;
6. a legacy count-only inquiry fails closed after removal;
7. missing all freshness-floor metadata fails closed;
8. existing resolver relation/observation/partition rules remain unchanged.

A dedicated copied-state study uses separate baseline and candidate Python processes against copies of the same pinned autonomous state. Both stage unrelated evidence, grounding evidence, and a matching stale outcome before the inquiry. The disposable stores then remove a fixed historical prefix and record one genuinely fresh outcome.

Expected contrast:

- current production positional resolver rejects the fresh outcome because its shifted list index is below the old floor;
- candidate sequence resolver rejects the stale outcome but resolves the genuinely fresh outcome;
- neither path advances the organism cycle;
- the pinned source file stays byte-identical.

Passing this test removes the native resolver's positional-newness blocker only. It does not authorize archival.

## Next retention boundary

After this prerequisite is verified/deployed, physical retention still needs a reference-preserving archive contract. In particular:

- active inquiry grounding/outcome evidence must remain resolvable;
- archived IDs must not become misleading generic evidence authority;
- all still-referenced episode IDs need an explicit hot/archive lookup rule;
- Planning Lab, world-model, semantic-memory, interaction, and self-model references need preservation policy;
- archive deletion must not manufacture/erase Phase 42 progress;
- compact-state/journal work on the separate storage branch must be coordinated rather than bypassed.
