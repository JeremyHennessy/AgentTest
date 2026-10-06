# Copied diagnostic-writer recovery integration

Status: review-only, default-off integration on top of PR #205. Production
workflows do not pass the new flag, so the ordinary heartbeat path remains
unchanged. No live state, journal, schedule, provider, score, world authority or
Observer behavior is altered by this branch.

## Scope

The exact-event recovery engine is copied into `src/agenttest` for import by the
real diagnostic scripts. Both `experiment_design_eval.py` and
`blocked_attention_eval.py` gain one explicit option:

`--copy-recovery-root <ABSENT-DIRECTLY-CREATED-COPY-ROOT>`

Without that option they use the preexisting save-then-append implementation.
With it, the requested state path must be the marked copied store's
`organism.json`; otherwise the command fails before diagnostic work.

The copied recovery store must be created explicitly through
`RecoveryStore.create(..., copied_only=True)`. Creation rejects an existing
destination, symlink aliases and unsupported non-POSIX environments.

## Ordering guarantee under review

When recovery mode is opted in, each diagnostic does this before loading state
for its normal cache decision:

1. open the marked copied recovery store;
2. recover any exact retained pending transaction;
3. read the settled snapshot;
4. evaluate the existing diagnostic and compute its existing context hash;
5. reuse the existing diagnostic or, if new, freeze the exact state/event bytes
   and commit them through the recovery engine.

That ordering matters. A prior process may have already saved a completed
diagnostic before losing its journal append. Recovering after the cache check
would reproduce the gap documented by PR #204.

Operation identity is deterministic from diagnostic kind, diagnostic ID and the
full context hash. The retained exact event bytes carry the original timestamp;
recovery never creates a replacement timestamp.

## Acceptance tests

The adapter suite uses only temporary copied stores and frozen clocks. It checks
both real diagnostic scripts.

- Opt-in success must produce byte-identical state, journal, output sidecar and
  stdout compared with the existing default path.
- Interruption after snapshot replacement must leave a pending exact intent;
  retry must repair the journal before cache reuse and must not duplicate it on
  later retries.
- A pending experiment-design transaction must be recovered when the attention
  diagnostic is the next command, before that second writer starts new work.
- A foreign/unowned journal tail must fail closed before cache reuse or output.
- A state path outside the marked recovery root must be rejected.
- Default operation must create no recovery metadata.

PR #205 separately covers partial writes at every event-byte prefix, exception
boundaries, SIGKILL during commit and SIGKILL during recovery. These adapter
tests do not relabel those storage-level subcases as live Ora evidence.

## Explicit limits

This branch still does not enable recovery in the heartbeat workflow. It does
not adopt an existing live state directory, measure the current full-size live
store, solve runner loss before git push, guarantee power-loss durability, or
cover every StateStore/CLI/interaction/reconciliation writer.

The diagnostic scripts deliberately keep their current indented snapshot
serialization in both default and copied-recovery modes so transaction recovery
is not mixed with a formatting change. A later formatting-only proposal may
route them through compact serialization after recovery correctness is settled.

No recovery proposal may merge until remaining writer classes, rollout/adoption,
pending-transaction rollback, full-size overhead and remote-runner persistence
boundaries are independently reviewed.
