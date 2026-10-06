# Copied experiment-outcome recovery

Status: review-only and explicit-copy-only. This stage adds recovery semantics to
`AgentCore.record_outcome` only. The central heartbeat cycle, human interaction,
native state-only APIs and production workflows remain unchanged.

## Default behavior

With no recovery root, `record_outcome` preserves its existing contract:
completed experiments reject a second recording attempt, state is saved through
`StateStore`, then one `experiment_outcome` event is appended.

## Copied recovery behavior

An explicit `copy_recovery_root` must own the AgentCore StateStore path. The
pending exact transaction is recovered before the experiment is inspected.

For a fresh outcome, the exact state and event bytes are committed under stable
operation identity `experiment-outcome-<experiment id>`.

If recovery settles a previously interrupted exact commit, an identical caller
retry is acknowledged by returning the single persisted experiment reflection.
This is necessary because the durable state already says the experiment is
completed. A retry with a different outcome, evidence strength, missing
reflection or ambiguous reflection fails closed and does not modify files.

The retry rule exists only in copied recovery mode. It does not weaken the
existing default duplicate-outcome rejection.

## Acceptance gate

Temporary-copy tests require:
- initial recovery-mode state, journal and returned reflection to exactly match
  the default path under a frozen clock;
- an interruption after snapshot replacement to recover the exact event before
  completed-state handling;
- repeated identical retries to return the persisted reflection without a second
  journal row;
- conflicting outcome or evidence-strength retries to fail without mutation;
- default completed-outcome behavior to remain an error;
- recovery root ownership to be enforced.

## Limits

No CLI command enables this path yet. No live state is adopted. This stage does
not cover Core.cycle, human interaction, power loss, runner disappearance,
full-size overhead or rollback with a pending live transaction.

Native evidence/inquiry/resolution persist methods remain intentionally
state-only and are not routed through paired-event recovery.
