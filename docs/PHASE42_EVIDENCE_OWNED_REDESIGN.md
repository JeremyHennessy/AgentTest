# Original Ora / AgentTest: evidence-owned Phase 42 redesign

**Scope:** AgentTest only. AI-Research is a read-only scientific reference.
**Source baseline:** AgentTest main at fc4f2620734fd90ac2f3783b1b9b0b297086ca84.
**Status:** new bounded research implementation, not an activated live heartbeat or a claim of beneficial autonomy.

## Why make a new learning loop?

The historical Phase 42 often selected a question *after* the Planning Lab had
already acted. A foreground question therefore was not necessarily the owner of
the world action. Historical natural-resumption metrics reported no confirmed
evidence-caused resumptions, and matched tests showed that selected questions
could change without changing natural actions. Increasing resumption counts or
tuning scores would not close this causal gap.

The AI-Research Passes 1–28 synthesis at
[bfbd53c](https://github.com/JeremyHennessy/AI-Research/blob/bfbd53c7b9ad92e03f15f3d31a133337b19ad8de/docs/artificial-life/UNIFIED-RESEARCH-SYNTHESIS.md)
recommends separating observed organization, useful function, history-conditioned
adaptation, descendant transmission, net benefit and higher-level claims. This
work addresses **only a narrow history-conditioned action-selection mechanism**.
It does not adopt EERC as an architecture mandate or combine different
experiment outcomes into one organism claim.

## What is implemented

A new isolated policy in src/agenttest/causal_investigator.py receives:

1. the current public observation (position, inventory and visible entities);
2. the currently available public action menu;
3. its own preceding, completed inquiry/receipt history.

It cannot import hidden simulator rules, original Ora's prior agenda scores,
world maps, private entity types, rewards, benchmark answers or a model provider.
For each currently available action it derives an empirical categorical outcome
distribution using shared action-family evidence and more specific local evidence.
It freezes that forecast and independently chooses an investigation based on
uncertainty, untested local contexts and the observed cost of repeating blocked
or ineffective actions. Its choice is not prescribed by a study harness. It may
choose a poor action; all adverse outcomes are retained.

The separate experiments/phase42_evidence_loop.py holds the existing finite
open-object world. **Only this runner** can call the simulator's transition
function. The runner validates the complete selected command against the
public candidate menu, performs exactly one transition, classifies the
observed effect, and saves a full receipt with the selected owner and
pre-action forecast in one atomic research capsule. The next selection sees
that completed outcome.

The capsule is source-hash-pinned, size- and action-bounded (64 steps, 16 MiB),
revision-checked, fully replay-audited from seed and public outcomes, and
protected by an exclusive research lock. Repeated request IDs return committed
receipts without taking a second action. Unknown/stale requests fail without
writing. A changed policy/simulator source, forged selection or mismatched
history causes an explicit rejection. It never accepts the original
state/organism.json path. Each study uses unique temporary files; it does not
restore, truncate, compress or modify original history.

## Evidence and limitations

- Four already-existing mirrored layouts can be run under identical budgets.
  They are four authored configurations, **not** statistically independent new
  worlds, biological individuals or lineages.
- Every action has a pre-action predictive distribution and an observed outcome.
  Report prequential Brier score and a weak uniform-probability null. The null
  is not a state-of-the-art adaptive baseline.
- Re-select at the *same public state* with all prior memory withheld to record
  whether memory changes the choice. A difference establishes decision
  sensitivity only, **not** superior outcomes.
- Read every capsule back and reconstruct every owner, command, action receipt,
  public frame and historical checksum from the unmodified world source. This
  establishes bounded replay/ownership, not power-loss recovery under every OS.
- No autonomous organism, endogenous reproduction, novel useful function,
  continuous world, verified general learning, sentience or consciousness
  follows from this pilot. A synthetic test pass is not a scientific positive.

A later independent comparison must preserve a genuine inherited Ora
inquiry/goal, match all common start states and total action budgets, and compare
held-out performance against context-matched baselines. It must not substitute
the new exploratory loop's favorable results or overwrite the older negative
Phase 42 evidence. A later checked integration may connect selected
investigations to ordinary Core under an explicit, reversible gate; this
research change does not secretly activate it.

## Reproduce offline (no API or paid resources)

From an exact, reviewed repository checkout:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest tests.test_phase42_evidence_owned -v
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python experiments/phase42_evidence_loop.py study --steps 12

Or, using an explicit **new scratch directory**:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python experiments/phase42_evidence_loop.py init --capsule /tmp/ora-owned-unique/one.json --seed 1
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python experiments/phase42_evidence_loop.py step --capsule /tmp/ora-owned-unique/one.json --request-id R000001 --expected-revision 0
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python experiments/phase42_evidence_loop.py inspect --capsule /tmp/ora-owned-unique/one.json

The directory must exist and the capsule filename must be new. Do not reuse
an old checkpoint or bypass source/revision/identity checks.

## Release boundaries

- Existing AgentTest main, autonomous growth state, journal, heartbeat
  controller, Observer HTML/CSS/JS and approved presentation remain unchanged
  by this branch.
- Storage PR #262 is a separate draft. Do not change its branch, assume a
  compressed snapshot is deployed, or compound the storage cutover with new
  learning authority.
- The new route must pass exact-head CI, full inherited preservation checks,
  owned-action/replay invariants and a fresh standalone exploratory study.
- Publication of code and a green Actions run do not activate this route in
  original Ora. A later live cutover needs a separate, explicitly defined,
  reversible authority boundary, a heartbeat checkpoint and exact comparison
  against untouched natural behavior.
