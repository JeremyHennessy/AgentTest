# Ora: current operations and new-world readiness

## Scope and date

Verified checkpoint: **2026-10-06 23:55 UTC**. This is a dated operational
checkpoint, not a promise that branch heads or live counts remain unchanged.
Recheck the linked branches and exact-commit checks before using this handoff.
This document supersedes the old offline kit as an operational entry point;
it does not rewrite or invalidate that historical archive.

## Authoritative sources

- Production code: [`main` at `4671b811c854223ff15ad5d3c520c511c6434421`](https://github.com/JeremyHennessy/AgentTest/commit/4671b811c854223ff15ad5d3c520c511c6434421).
  [Exact-main verification](https://github.com/JeremyHennessy/AgentTest/actions/runs/37533070347) succeeded.
- Persistent state: [`autonomous/growth` at `0a043b7e7669dad6985c24b19d3c628ab2ee90d9`](https://github.com/JeremyHennessy/AgentTest/commit/0a043b7e7669dad6985c24b19d3c628ab2ee90d9), cycle 5909.
  [Growth run](https://github.com/JeremyHennessy/AgentTest/actions/runs/37548936688) passed 412 tests,
  30/30 behavioral preservation, Phase 42 integrity and journal-scope checks,
  and persisted successfully. A later heartbeat may supersede this checkpoint.
- Copied richer-world compatibility: [draft PR #213](https://github.com/JeremyHennessy/AgentTest/pull/213),
  head `b3da508f6ebadc778cdb3cca5b9903997685d023`, based on that production commit.
  [Exact-head](https://github.com/JeremyHennessy/AgentTest/actions/runs/37543655594)
  and [PR verification](https://github.com/JeremyHennessy/AgentTest/actions/runs/37543662592)
  passed, including 422 tests. The ten additions are research scripts,
  experiments and tests; no production source or live workflow is changed.
- Historical archive: [Ora-Handoff offline kit v2](https://github.com/JeremyHennessy/Ora-Handoff/releases/tag/ora-offline-kit-v2-20261006),
  repository checkpoint `5c073f57e5cce21a6efcd8428a357f90b38a0e22`.
  Its old production/candidate status is not the current deployment queue.
- Recovery PRs #204–208 were intentionally closed unmerged. They are retained
  investigation for a future persistent-local-service architecture, not an
  outstanding merge queue. See the [closure rationale](https://github.com/JeremyHennessy/AgentTest/pull/208#issuecomment-6025625479).
- A separate [draft Observer PR #196](https://github.com/JeremyHennessy/AgentTest/pull/196)
  contains broader refresh/race and layout work. It retains its rendered-browser
  review hold. This handoff/disclosure update does not claim those changes are
  deployed or resolve that hold.

## What is live

The current Bounded Action / Planning Lab, persistent state and journal,
existing memory and agenda, deterministic evidence-linked interaction,
protected diagnostics, and owner-authorized GitHub interaction transport are
live. Growth and interaction share the same versioned concurrency group.
The current workflows do not depend on an external model API.

The public/native resolution dispatcher is present but disabled by default.
No richer challenge world, copied challenge action capability or automatic
native-inquiry activation has been granted to the live heartbeat. Do not add
activation flags as part of maintenance or a copied experiment.

## What has only been tested on copies

The richer 5×5 object world, persisted public recorder, epistemic selector,
single-use action capability and bounded closed-loop study are research.
Earlier frozen-policy tests found 83.3% versus 40.0% inquiry falsification;
30/30 mature copied cases resolved (25 falsified, 5 supported). Those figures
are historical copied-study evidence, not live progress and not a new
measurement at this checkpoint. PR #213 verifies current-code compatibility;
it does not itself establish a causal later-choice benefit from retained
memory or natural suspended-inquiry resumption.

Any next study must identify its exact source commit, input-state commit/hash,
seed list, horizon, observations and exclusions. A historical input tested on
current code must remain labelled historical. A control that withholds a new
outcome measures both that outcome and its normal completion consequences;
it is not interchangeable with a pure association-memory ablation.

## Current cautions

- Phase 42 remains an evidence question. Cycle 5909's retained telemetry has
  127 qualified alternatives, all lower-priority, zero genuine resumptions
  and zero handoff/selection mismatches. Zero resumptions alone is not a
  routing defect. Do not force priority or manufacture a live milestone.
- The state and journal are large: the pinned Git tree records 90,905,164
  state bytes and 81,474,312 journal bytes (86.69 and 77.70 MiB). Compact
  StateStore serialization is merged, but storage growth still needs writer-
  sequence and lossless-preservation review. Formatting cannot bound an
  indefinitely growing history. Never truncate or summarize away memory,
  silently alter replay semantics, or roll state backwards.
- Test-suite success is not evidence of consciousness, general autonomy or
  new-world readiness. Report null and adverse copied-study results.

## Readiness gates and evidence needed

These are acceptance questions, not a count-based score. At this checkpoint
**new-world readiness is not established and activation is withheld**.

1. **Evidence-caused choices:** a predeclared copied study compares identical
   later observations and candidate sets with relevant evidence retained or
   withheld. Controls remain valid and preserve unrelated history. Report
   choice changes and their direction; separate selector-only findings from
   ordinary native/full-cycle outcomes. No reward or authored solution.
2. **Revisits and contradicted expectations:** record whether an actually
   suspended inquiry becomes relevant and is naturally revisited. Report
   zero opportunities or zero revisits honestly. Distinguish a repeatedly
   refuted objective, a failed action expectation, and useful repeated
   falsification; they are not the same metric. A fabricated resumption is
   never an acceptance shortcut or Phase 42 credit.
3. **Authority and containment:** use exact source/evidence freshness checks,
   bounded single-use capabilities, public observations, explicit action
   budgets and restart/replay tests. Live flags remain off while assessing
   these properties. Verify that copied files cannot become live authority.
4. **Persistence and sustainability:** demonstrate full decoded state and
   journal-event/order parity for any serializer change, including cold
   restarts, diagnostic cache paths and historical byte-prefix preservation.
   Document residual unbounded growth and a lossless long-term design; do not
   substitute the closed recovery prototype for a current production fix.
5. **Current baseline and operations:** validate the exact candidate against
   current main, run the base-owned preservation gate, check the exact remote
   commit and all required CI, and inspect interactions/heartbeat for races.
   The observer and handoff must distinguish live abilities from experiments.
6. **Bounded rollout proposal:** specify what becomes enabled, action budget,
   data sources, stop conditions, monitoring and rollback. Rollback disables
   new authority while preserving every committed memory and journal event;
   it must not restore an older state snapshot. Keep the previous live lab
   available. The proposal must state unresolved results and prerequisites.
7. **Separate activation approval:** the owner reviews the bounded rollout
   proposal and explicitly authorizes activation. Maintenance permission,
   research success and a request to become ready do not grant this approval.
   No new provider, credentials, infrastructure, spending or expanded access
   is included in these gates.

A natural Phase 42 milestone is evaluated on its own evidence. It must neither
be asserted from copied-world activation nor replaced with an artificial
resumption threshold solely to mark this checklist complete.

## Safe next operational step

Start from current main and the preserved research branch, recheck overlap,
and retain separate reviewable changes for research, storage and observer
work. Keep research default-off. Before any proposed activation, publish the
exact tested commit and completed/unsatisfied gates so that the owner can
make the separate activation decision without relying on archived advice.
