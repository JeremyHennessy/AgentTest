# Historical context-novelty revision at b189d656

This is the preserved context-signature recipe tested at `b189d656`. Its full-state
preflight found no structural change and created no new case. It was never enabled
live. The [original read-only run and attached artifact](https://github.com/JeremyHennessy/AgentTest/actions/runs/37641510899) retain that
negative result. The separately versioned [observed-effect follow-on](current-world-effect-revision.md)
changes the admission unit while keeping this recipe's historical reader.

This is an explicit finite representation improvement, not a correction of the
original null result. The earlier lane correctly abstained with its frozen first
32 observations. The new lane version is `current-world-investigation-v2`; its
revision recipe is `observed-transition-revision-v1`. The pure grounded policy,
model grammar, likelihoods, rational arithmetic and selection threshold are
unchanged.

## Scope of this iteration

An initialized lane with one null case, no pending authority, no prior action,
and its original two-action allowance may form one discovery revision. The old
v1 null checkpoint is also eligible after the gate-off heartbeat marked it
`disabled`; this is a deliberate one-time version migration, not a budget reset.
After the revision is attempted, future flag toggles cannot repeat it. A disabled
v2 lane stays disabled. Other terminal or pending states do not gain authority.

The original discovery, cohort and case bodies/hashes remain unchanged. New
fields record the revision attempt and one immutable revision. Historical cases
without a revision ID still resolve the original cohort. A new case carries its
own revision ID/hash, and its pending authority binds those fields. Existing
rollback metadata is preserved separately from any later revision rollback.

## Grounding and evidence accounting

1. Read and validate the complete same-world observation history with the existing
   exact source-ID/body deduplication. Preserve its order and every actual row.
2. Starting after the original discovery prefix, select at most 32 earliest rows
   whose `(before_context, action, after_position)` signature has not appeared in
   discovery or earlier additions. Every kind of new outcome qualifies, including
   contradictory outcomes. IDs, forecast scores and desired actions do not rank
   the additions.
3. Append those observations to the original discovery, with a maximum of 64 rows.
   Rebuild the unchanged finite policy once. Record parent hashes, promoted
   source IDs/body hashes, the complete source cutoff/hash, cohort and structural
   differences. No repeated expansion is attempted to obtain a selection.
4. A new case is permitted only when concrete model structures or action
   availability change. Different support counts, loss rankings, model ordering
   or posterior weights alone do not qualify. No structural change is recorded
   truthfully without a new case.
5. Recompute the revised cohort's posterior from every actual row outside that
   revision's discovery-ID set. Promoted rows now have the discovery role and are
   excluded from posterior evidence. Other rows retain their original order and
   are applied once. Old posterior weights are not carried forward and updated
   again. Old cases retain their original partition for verification.

This is adaptive hypothesis construction from real observations, not a new claim
of unbiased validation or improved learning. A revised case can still return
null or block on the unchanged exact-rational or storage limits.

## Existing execution boundary and limits

Preparation is staged in memory and checked before installing the new checkpoint.
A rejected oversized case is not left appended for Core to save. A valid bounded
model revision can remain as provenance when its later evaluation blocks; an
oversized revision retains only a compact failed-attempt record. Previously
committed case records are preserved in either situation.

A pending authority is never revised. The existing previous-heartbeat seam,
world/evidence/execution checks, remote request claim and final state/journal Git
commit remain in force. The new case's cohort is resolved by immutable revision
identity both for execution and its outcome/belief update. New completed receipts
also verify this link; old receipts remain readable without matching today's
execution source hash.

The original two-case and two-action ceilings do not reset. The recorded first
null occupies one case slot, leaving at most one new case and therefore at most
one additional action in this iteration. The 8,192-observation ceiling, completion
row reserve, 4 MiB checkpoint limit and 256-digit rational bound are unchanged.
No workflow gate, provider, world, access setting or live state is changed by
this source implementation.

## One read-only preflight and focused checks

`scripts/current_world_readiness.py` now accepts the preserved initialized lane.
It copies only the required planning fields and bounded checkpoint into memory;
never consumes authority, calls the actuator, opens a writable StateStore or
writes source state/journal. Its report binds raw SHA256 before/after, candidate
execution content and script content. It reports old body/hash preservation,
new model structures, complete D/U ID partitions, promoted IDs, selected/null/
blocked outcome, and byte/rational usage. A repeated inspection identifies an
existing revision without claiming a new preparation. Output aliases of the
source organism or its actual sibling journal remain rejected.

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B scripts/current_world_readiness.py \
  --state /path/to/full/preserved-organism.json \
  --expected-sha256 SHA256_OF_THAT_FULL_SNAPSHOT \
  --output /tmp/current-world-revision-readiness.json
```

The full actual snapshot is pinned by Git commit and raw blob identity in the
read-only admission workflow. Its raw SHA256 is derived only after that identity
check and is verified again after inspection. A sampled projection cannot establish admission. The full-history run and exact-head CI precede any reviewed
one-additional-action rollout. Local checks are limited to changed accounting,
immutability, authority/budget behavior, preflight non-mutation and existing
relevant continuity/readiness tests; there is no new study or benchmark framework.
