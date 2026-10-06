# Ora persistence recovery review - 2026-10-06

Status: characterization only. No runtime recovery implementation, activation,
state migration, journal rewrite, or memory rollback is included. Keep this
review branch unmerged while the recovery contract is designed. Passing these
tests demonstrates the documented behavior, including unsafe behavior; it is
not a recovery acceptance result.

## Preserved production checkpoint

- main: `8f90f8b6157c88bc81a014cbeba668155859df3a`
- tree: `658d355163fc2e87fd2a40c3c65cac6a0374aa59`
- state.py: `ae4697869e5870d2cdcdc3f6e8f8384e284fc69d`
- experiment_design_eval.py: `ae8bd08b4caa8d25f2011a79c23d1c22707cb90b`
- blocked_attention_eval.py: `b86f7fdc83045b3204da876ef395e0b4ec1f07be`

These writer identities were checked against pinned GitHub source before the
review. The local development workspace uses retained V4 source plus the exact
current compact StateStore; it is NOT a full restoration of current main.
Local focused results are supplementary. Hosted CI on this branch's exact head
is the authority for compatibility with all current production source.

## Writer and reader inventory

StateStore owns one snapshot writer (temporary file followed by replacement)
and one journal append method. Core cycles/outcome recording, human interaction,
CLI proposal/review paths and verified-change reconciliation use these APIs.
Some opt-in native methods intentionally persist state without a journal append;
therefore not every state save is evidence of a missing journal event. Existing
counterfactuals use isolated stores. Do not activate those paths for this review.

Two normal heartbeat scripts independently write the same authoritative files:
`scripts/experiment_design_eval.py` and `scripts/blocked_attention_eval.py`.
Each replaces the state before appending its diagnostic journal event. Both
bypass StateStore, use indented state JSON, and reuse an already completed
matching diagnostic on retry. A StateStore-only repair cannot cover these paths.
They can also re-expand a compact snapshot during the normal heartbeat sequence.
This is formatting inefficiency, not evidence that decoded memories were lost.

CLI/result sidecars and read-only Phase42 report outputs are not authoritative
state commits. The replay diagnostic builds isolated fixtures and parses journal
lines; it is not a live restoration engine. No replay study is rerun here.

## Reproduced failure matrix

All cases use synthetic temporary stores and controlled I/O exceptions. There
are no Core.cycle calls in the added tests, live-state accesses, network calls,
external providers, new simulator observations, or archived trajectory replays.

| Case | Baseline result | Recovery implication |
| --- | --- | --- |
| Snapshot replacement fails | Previous state and journal bytes survive; temp file may remain | Never promote an orphan temp file merely because it exists |
| Partial temporary snapshot then reload | Committed snapshot is loaded, temp is ignored | Preserve old committed state until a validated commit boundary |
| Snapshot committed, journal open fails | New snapshot survives; reload does not reconcile missing event | Need durable exact event intent for legitimate replay |
| Partial journal append | Valid prior prefix survives; later append concatenates to malformed tail | Detect incomplete tail before accepting another append |
| Complete JSON record lacks final newline | Next append concatenates two JSON documents | Newline framing is part of the commit boundary |
| Repeated raw append | Identical event is appended twice | Raw append alone provides no idempotency |
| Invalid committed JSON | Load raises without repairing files | Fail closed; do not replace corruption with fabricated state |
| Missing snapshot with existing journal | Load returns fresh initial state without interpreting journal | Distinguish a genuinely empty store from interrupted/lost snapshot |
| Either diagnostic fails before state replacement | Old state/journal survive; retry can create diagnostic once | Existing pre-replacement failure behavior is preservable |
| Either diagnostic saves then journal open fails | Completed diagnostic is saved; retry returns cached result and leaves event missing | Retrying the command is not journal recovery |
| Either diagnostic partly appends then retries | Malformed tail remains; cached retry does not repair it | Handle recovery before cache short-circuit |
| Either diagnostic succeeds after compact save | Snapshot is indented again, decoded prior fields preserved | Compact StateStore alone does not compact the final heartbeat artifact |

The four diagnostic tests each exercise both direct writers. The twelve test
methods are characterization cases, not twelve fixed failure modes. A green
run must not be described as proof of crash consistency, power-loss durability,
or absence of historical live gaps. No live-loss claim is made.

## Reused evidence and limits

Existing dispatcher tests already establish saved-closure survival across an
injected append failure and resolver-level duplicate rejection. They remain
unchanged. This review expands the boundary inventory to raw appends, framing,
missing snapshots, direct diagnostic writers and cached retries. Resolver-level
idempotency does not imply raw journal append idempotency.

No event is reconstructed from a later timestamp, current state or guessed
content. No damaged historical tail is discarded. No old raw journal is compacted.
No attention weights, inquiry choices, counters, workflows, Observer UI, schema,
external APIs, credentials, spending or world permissions are changed.

## Next bounded implementation contract (not implemented here)

First define a transaction boundary shared by every authoritative writer. Persist
exact intended event bytes and their identity before declaring an associated
state/event commit recoverable. Account explicitly for legitimate state-only
operations and existing same-cycle multiple events. A restart must distinguish
an uncommitted temp snapshot, a committed snapshot with a pending exact event,
a partial append, a completed append and a previously completed recovery.

Require tests for repeated recovery and interruption during recovery itself,
old-history prefix preservation, no duplicated semantic outcome/IDs, explicit
handling of missing/corrupt files, and default-off world/provider boundaries.
Simulated exceptions are not enough to claim power-loss durability. Storage
format changes must include a code-rollback route that never rolls memories back.

Do not improvise a partial live fix by catching errors, blindly retrying append,
truncating a journal, resetting state, or routing only one writer through new
infrastructure. If no original event bytes exist, report the inconsistency
instead of synthesizing history. Keep any formatting-only repair separate from
a transactional-recovery change and verify its normal heartbeat result.

Run the added tests with:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -p 'test_persistence_failure_boundaries.py' -v
```
