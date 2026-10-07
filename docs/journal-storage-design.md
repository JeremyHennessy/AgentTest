# Lossless journal storage: inventory and proposed next boundary

Status: **design only, 2026-10-07 UTC; not implemented or activated**.
Inventory is for all 122 blobs at main
`4671b811c854223ff15ad5d3c520c511c6434421`. The separately tested diagnostic
snapshot-formatting correction does not change this journal contract.

## Exact repository writer inventory

Physical output today is the single sibling `journal.jsonl` chosen from the
snapshot's directory. There are three physical append implementations:

1. `src/agenttest/state.py:StateStore.append_journal` writes compact sorted JSON
   plus one newline, with UTF-8 text append. Its callers are:
   - `src/agenttest/core.py:AgentCore.cycle`: `cycle` events, after saving state.
   - `src/agenttest/core.py:AgentCore.record_outcome`: `experiment_outcome` events.
   - `src/agenttest/interaction.py:run_interaction`: `human_interaction` events;
     it also invokes the core cycle. Request IDs protect the existing interaction
     replay path and must survive any new layout.
   - `src/agenttest/cli.py`: `propose-change`, `review-change`, `diagnose-change`
     append their respective change-proposal/review/diagnostic events when a new
     record is created.
   - `scripts/reconcile_verified_change.py`: `verified_intervention_reconciled`
     after a new accepted-change receipt is saved.
2. `scripts/experiment_design_eval.py:main` directly appends a
   `system_diagnostic` event for a new experiment-design diagnostic.
3. `scripts/blocked_attention_eval.py:main` directly appends a
   `system_diagnostic` event for a new attention-control diagnostic.

The two direct appenders currently use JSON's default spaces, sorted keys, UTF-8,
and a newline. The serializer correction changes neither. Any future common
append adapter must preserve each writer's current event bytes rather than
incidentally standardizing them.

Workflow transport:

- `.github/workflows/growth.yml` executes the cycle, proposal/review diagnostics,
  and both system diagnostics; it stages all `state/` files and pushes growth.
- `.github/workflows/interact.yml` executes interactions, persists the response
  sidecar, and stages all `state/` files. Remote request claims/response replay
  are separate safeguards, not a general journal transaction.
- `.github/workflows/reconcile.yml` executes verified-change reconciliation and
  stages all `state/` files.

Important concurrency prerequisite: growth and interaction use
`agenttest-autonomous-growth-v2`, while reconciliation still uses
`agenttest-autonomous-growth` at the audited main commit. They are not one shared
workflow lock. Before rotation is activated, all relevant writers need a verified
single-writer boundary or an explicitly tested conflict protocol. A workflow
group also does not lock ad hoc CLI writers outside Actions. This design makes
no assumption that the current installation is multiwriter-safe.

## Exact repository reader inventory

- `src/agenttest/diagnostic_replay.py:run_fixture` reads
  `store.journal_path.read_text().splitlines()`, skips blank lines, parses every
  remaining line, and includes the complete ordered event list in its normalized
  deterministic-fixture result. It is an isolated fixture reader; the current
  live organism is loaded from the snapshot, not reconstructed from the journal.
- `scripts/phase42_experiment_routing_eval.py:main` reads `--records` as one JSON
  value or JSONL. It can consume a journal supplied by the operator, and requires
  an exact-cycle snapshot for ID resolution. A segmented journal must not cause
  it silently to inspect only the final segment.
- Existing direct physical-file assertions occur in `tests/test_core.py`,
  `test_phase42_repairs.py`, `test_interaction_request_identity.py`,
  `test_public_observation.py`, and `test_public_resolution_dispatch.py`.
  They cover file existence, final events, exact nonmutation/idempotence, or the
  existing state-save/journal-failure seam.
- The new `scripts/storage_growth_study.py` and its tests read raw journal bytes,
  inventory ordered JSONL events, and verify an exact original prefix.
- `index.html` fetches snapshot, last-interaction, and resumption-opportunity
  JSON files. It does not fetch/parse `journal.jsonl`; its “Growth journal” link
  points to the inspection PR. Thus no observer journal parser was found.
- Growth/interaction/reconciliation workflows stage and transport state files;
  they do not themselves parse the journal body.

This is a repository inventory, not proof that there are no external human
scripts or consumers of the raw journal URL. Their contract needs explicit
notice before changing what that URL represents.

## Smallest prospective layout worth testing

Do not prune, deduplicate, truncate, rewrite, or rename the existing journal.
Freeze its exact bytes as the legacy prefix and add new append-only segments
for **future** events. That avoids an in-place migration of the 77.70 MiB
cycle-5909 journal. A read-only identity manifest can bind that frozen prefix
by path, exact byte length, SHA-256, and line/event counts.

Proposed implementation boundary for a separate patch:

1. Introduce a common logical journal iterator that yields legacy-prefix bytes
   followed by every ordered segment. Provide decoded-event iteration and an
   explicit export of the complete logical JSONL stream. Use line/byte sequence
   positions, not cycle numbers, to establish order: multiple event types can
   share a cycle. Preserve blank lines, CRLF, Unicode, and the exact original
   final newline where present. Refuse an incomplete/invalid legacy tail; do
   not repair or discard it automatically.
2. Route all three physical append implementations through one adapter accepting
   the already serialized line. Keep event contents, IDs, key order, spaces,
   newline and timestamp decisions at their existing callers.
3. Keep immutable sealed segments and one active segment under `state/`, with a
   conservative proposed rollover target such as 8 MiB. This is a design value,
   not an active user limit. An individual event exceeding the target needs a
   specified, tested policy; silently splitting a JSON event or allowing a blob
   over the hard publication budget is unacceptable.
4. Publish segment identity/order and its uncompressed byte digest in a versioned
   manifest. Verify the complete manifest plus every referenced file before
   committing/pushing the growth branch. A successful Git commit gives readers a
   consistent published generation; it does not make local multi-file operations
   transactional or durable against power loss.
5. Update both existing reader paths and their tests to the logical iterator.
   Keep raw legacy-file access explicitly labelled as a prefix, and document
   the complete-stream export. Do not redefine `journal_path` silently to mean
   “all history” while returning only the active file.

Optional compression should be a later representation-only step: deterministic
gzip for **new sealed segments**, with both compressed integrity and exact
uncompressed SHA-256/length recorded. The reader must restore the original byte
stream and reject truncation, corruption, missing pieces, or order conflicts.
No production historical-journal compression or layout change is authorized by
this design document, and none has been performed. A bounded in-memory codec
experiment on the historical cycle-4599 journal compressed 59,944,566 bytes to
1,572,281 bytes and restored the exact original SHA-256. The source file stayed
unchanged. That result tests the codec on that input, not a segmented storage
implementation or its failure behavior.

## Failure and preservation obligations before implementation can be accepted

- Differential baseline/candidate comparison of the complete logical byte
  stream and decoded event sequence, not just the last segment or event count.
  Every legacy byte must still be present, once, in the original order.
- Every writer above, including direct diagnostic appends, interaction request
  replay, proposal cache hits, experiment outcomes and reconciliation receipts,
  must cross a rollover boundary under tests.
- Save/reload and subsequent ordinary cold-process cycles must preserve full
  state, results, evidence IDs, source references, duplicate-resolution guards,
  metrics and prediction/intervention accounting under matched observations.
- Check zero/one/many segments, boundary-adjacent and oversized lines, Unicode,
  old spacing/CRLF/blank lines, duplicate filenames/ranges, path traversal,
  malformed manifest, hash mismatch, truncated gzip and missing files.
- Inject failures before/after segment creation, append, seal, manifest replace,
  Git commit and push. Keep all uncertain bytes, report orphan/conflicting
  generations explicitly, and fail closed instead of guessing or replaying a
  possibly committed event. Do not invent a recovery protocol in this patch.
- Confirm the publication budget on every state blob and distinguish
  preflight failure before a state save from failure after it. Existing callers
  save snapshots before journal append, so an append failure can leave a saved
  cycle without a journal event. A segmentation patch must not claim to fix
  that gap or make it harder to detect. It cannot silently discard that cycle.
- Verify writer exclusion/conflict handling for every workflow and CLI route.
  Test interrupted publication and old-reader behavior explicitly.
- Run the unchanged main-owned behavior gate, full suite, copied-state study,
  and independent review. Post-activation inspection must show all expected
  segment files and matching manifest identities at one immutable commit.

## Hard file budget versus sustainable all-history storage

The 100 MiB GitHub blob cap is a per-file publication limit. Keeping each new
segment below it addresses that limit, not unlimited total storage. Compression
reduces repeated payload cost but cannot guarantee a fixed bound for arbitrary,
losslessly retained future history. The snapshot's historical collections also
continue growing even if the journal is segmented.

A sustainable architecture needs immutable, verified history objects plus a
bounded active/index working set and explicit, lossless hydration/export APIs.
It also needs a stated total-storage/resource budget and a capacity policy. If
all history must remain forever, capacity must be allowed to grow; if a fixed
budget is mandatory, eventual stop/approved capacity expansion must be explicit.
An external archive or persistent service could serve that role only under a
separately approved architecture, access and cost plan. No new infrastructure,
spending, credentials, Git history rewrite, retention loss, or revival of closed
recovery PRs 204–208 follows from this proposal.
