# Current-world heartbeat integration and bounded rollout

This is a bounded software rollout lane for the existing stateful planning world.
It is not activation of a new world, an external actuator, a provider, or a claim
of successful autonomous science. The CLI remains default off. The approved October 7 rollout enables
`CURRENT_WORLD_INVESTIGATION` in `growth.yml` for at most two owned actions in
the existing world. No repository variable or external setting enables this path.
After a terminal null, rejection or the two-action limit, the source-controlled
gate is returned to `false`; the checkpoint, history and current position remain.

## Ownership and evidence

The new lane owns its own observation-derived movement question and case. It does
not label the legacy agenda winner as the owner of an earlier planning action.
At the existing Core action seam, an enabled heartbeat consumes only a case
prepared by an earlier heartbeat. It then prepares the next case later in the
cycle. The first enabled tick prepares only. An enabled tick executes at most one
owned action and never also executes the legacy planning action.

`agenttest.grounded_policy` is the unchanged pure v2 policy and primitives. The
research package aliases those modules; its fresh-process bootstrap still captures
and pins both the research wrappers and all production source. Model language,
exact arithmetic, threshold, unresolved model and null behavior are unchanged.

The adapter reads actual planning position and transition observations. Inventory
and visibility are unavailable (`null`). It excludes base and transfer worlds,
keeps the first exact delivery of each source/source-ID pair, and rejects changed
duplicate bodies. It checks positions, chronological cycle numbers and observed
deltas. It does not read a route or map when selecting an action.

On first preparation, the first up to 32 unique genuine same-world transitions
become the frozen discovery prefix. Only subsequent rows update evidence; D is
never counted again as posterior evidence. The lane admits at most 8,192 unique
observations, two immutable cases and two internal actions. The checkpoint has a
4 MiB bound. The claim ledger permits at most 16 completed or abandoned requests.
These are finite rollout limits, not expanded scientific capacity or score tuning.
A null decision, exhausted budget, stale authority or provenance conflict stops
this lane without a runner-up action. An empty history remains an honest null.

Cases, attempts, outcomes and beliefs have stable logical IDs and content hashes.
Pending authority binds the owner, full case, relevant world/observation/evidence,
execution source content and Python version. Paths and inodes are not durable
identity. An unrelated interaction may advance the organism cycle while preserving
a prepared case; changed relevant evidence or execution versions reject it.
Completed historical receipts remain readable across fresh runners and upgrades.

The execution helper uses the real existing planning actuator once. It appends the
actual transition and execution, updates position, visit counts and learned model,
invalidates displaced plans, and cancels superseded objective precommits. It does
not claim a legacy goal, plan or objective was completed by the investigation.
Legacy memory and provenance remain intact.

## Remote commit and interrupted runners

The implementation extends the #210 pre-cycle request-claim pattern. It does not
introduce a local WAL, historical restore, or a separate writable executive store.
The existing shared GitHub concurrency group serializes growth, interaction and
reconciliation writers.

1. On the growth branch, persist a claim in `organism.json` for `heartbeat:<run_id>`.
   The ID deliberately excludes the retry attempt. The claim binds the cycle,
   organism content, journal bytes, pending authority, execution content, and
   exact supported invocation payload (mode, stimulus and flags).
2. Commit and push that claim before Core calculates any owned movement. Fetch
   the remote again. Core requires a clean checkout whose HEAD, fetched growth
   head, state bytes and journal bytes match the claimed snapshot.
3. Compute one cycle internally. StateStore atomically replaces `organism.json`,
   then Core appends its cycle journal event, as before. Those local operations
   are not a durable movement or a successful remote commit.
4. Before publishing, verify one completed request, exactly one matching cycle
   event, immutable case/attempt/outcome/belief bindings, and the current planning
   plus investigation checkpoint hash. Missing/duplicate/conflicting event or
   outcome evidence fails closed. Commit `state/` together and push once; fetch
   and check the remote commit before reporting preservation.

An uncertain or failed push stops the workflow. A fresh rerun first fetches the
remote. A matching completed request is a no-op, including delayed reruns after
later cycles. An identical pending claim may recompute from the exact unchanged
remote snapshot. Partially saved local state, changed source/payload/evidence,
conflicting IDs or an ambiguous journal do not authorize a retry. This guarantees
at most one durable committed result per request under the serialized writer
protocol; it does not claim exactly-once internal computation.

A crash after local state replacement and before journal append leaves only the
pre-cycle claim durable remotely. No scoped local outbox is needed: the workflow
never publishes that incomplete local result. A new runner starts from the remote
claim, not those discarded local files. Interaction Core calls and the verified
reconciliation writer refuse to modify an unfinished claim.

## Rollback and limits

Set the source-controlled workflow gate back to the literal `false` to stop new
preparation and consumption. The next
ordinary planning heartbeat retires prepared authority, preserves all committed
cases/events/memory, and uses the legacy planner at the current position. The lane
is deliberately not automatically reset or re-budgeted by a later flag toggle.

If a remote heartbeat claim is still pending, resolve it first from a clean fetched
snapshot. A compatible exact rerun is supported. To abandon an incompatible claim,
run the explicit operator command below with the exact pending request and reason,
review and commit/push its state change, then resume ordinary planning:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B scripts/heartbeat_request_claim.py \
  abandon --request-id heartbeat:RUN_ID --reason "Reviewed rollout disabled"
```

Abandonment preserves the claim as `abandoned_uncommitted`, retires any prepared
authority, and does not restore old position or delete history. It works after a
source upgrade, but rejects changed organism/journal input so ambiguous local
calculations cannot be mislabeled as abandoned remote work.

This integration intentionally suppresses the Core Phase 42 counterfactual replay
while owned authority is active; that diagnostic cannot silently substitute legacy
planning or create a second authority-bearing action. It reports the causality
comparison as unproven. Default-off behavior retains the existing diagnostic.

## Verification and rollout evidence

`tests/test_current_world_investigation.py` exercises actual policy selection from
explicitly synthetic real-actuator transitions, prior-tick ownership, null/stale
rejection, discovery/evidence separation, clean fresh-runner retry, interrupted
save/journal windows, failed final publication, completed-request replay,
reconciliation blocking, abandonment, interaction continuity and default-off parity.
`tests/test_planning_investigation_action.py` covers the helper and legacy resume.
Existing pure-policy, source-closure, provenance, memory and preservation suites
remain release gates. No live admission should be inferred from the synthetic
selected fixture. Recent real history must be read separately; genuine history
can legitimately yield null under the unchanged model and threshold.


## Full-history readiness before activation

The October 7 read-only snapshot at commit
`3449926e336cda1194a98a509990b03bfea2151b` contained 6,329 delivered same-world
observations (6,383 total) at cycle 6,500. The 8,192-row ceiling admits that corpus
size with 1,863 rows of current headroom; it does not truncate or resample the
history. This finite checked limit is not a general solution to future growth:
above-limit input remains fail-closed, and preparation reserves one row for each
remaining action (two on first admission).
The initial 4,096 ceiling was below this real corpus and was corrected before
publication. The 32-row discovery prefix, two-action budget, 4 MiB checkpoint,
256-digit rational bound, model class, likelihoods and threshold are unchanged.

Run the read-only check on the complete pinned organism file before enabling:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -B scripts/current_world_readiness.py \
  --state /path/to/full/organism.json \
  --expected-sha256 FULL_STATE_SHA256 \
  --output /tmp/current-world-readiness.json
```

The command rejects sampled projections, validates every unique same-world row,
separates the authentic first32 discovery prefix from all later evidence, and
runs unchanged evaluation/proof checks without executing an action. The report
binds the candidate execution-source hash and checks the input SHA256 before and
after; it never writes organism state or the journal. It reports
exact-context evidence counts, serialized checkpoint/rational sizes, and the
actual prepared/null/blocked outcome. An exact-rational overflow still blocks;
raising the observation ceiling does not relax arithmetic or selection semantics.
A sampled first32/last64 export cannot establish full-history admission. A new
snapshot needs its own raw SHA256 and full check; no enablement follows from a
synthetic capacity test or corpus row count alone.

## October 7 rollout admission

The full-history read-only check passed at candidate
`f2d22b6f4918731ee6f5063ca0bbf8b6836d8bf1` against the pinned cycle-6,500
state above. All 6,329 unique same-world rows were evaluated (32 discovery and
6,297 later evidence rows), and the raw source SHA256 was unchanged. The
checkpoint used 767,653 bytes of its 4 MiB limit; the largest serialized rational
used 244 of the allowed 256 digits.

The result was **null**, with no action executed. Only the south command had
sufficient explanatory diversity in the frozen discovery prefix, and its
information score was zero at the observed position `[1, -2]`. This is an honest
abstention, not evidence of learning benefit. The next natural heartbeat uses
its fresh actual state and may likewise abstain or reject a changed context. No
choice, discovery prefix, score or threshold is altered to produce activity.

The exact report is [current-world-readiness-20261007.json](current-world-readiness-20261007.json).
The [read-only admission run](https://github.com/JeremyHennessy/AgentTest/actions/runs/37631489016)
used zero world actions. Live receipts will be reported after the bounded rollout;
this preflight alone does not establish a live action or a durable outcome.
