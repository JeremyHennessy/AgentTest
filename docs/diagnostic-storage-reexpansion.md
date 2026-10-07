# Diagnostic writers undo compact snapshot storage

Investigated 2026-10-07 UTC against main
`4671b811c854223ff15ad5d3c520c511c6434421`. The two production changes are
the JSON formatting arguments in `_write_json_atomic` in
`scripts/experiment_design_eval.py` and `scripts/blocked_attention_eval.py`.
No state, journal, retention rule, cognitive policy, or recovery implementation
is changed by this patch.

## Cause and bounded correction

`StateStore.save` already produces compact, sorted JSON. In the growth workflow,
the two system diagnostics run after the cycle and proposal commands. On a
cache miss, each diagnostic adds its ordinary evidence record and rewrites the
entire snapshot using its own atomic helper. Those helpers still used
`indent=2`, so the final saved snapshot became pretty-printed again.

Both helpers now use `separators=(",", ":")`. UTF-8, default ASCII escaping,
sorted keys, trailing newline, temporary path, replacement order, timestamps,
cache identity, records, and journal append behavior remain unchanged. The same
helpers also format their small diagnostic report files compactly. Their CLI
stdout remains pretty-printed. Calling `StateStore.save` in their place would
add migrations/timestamp behavior, so this patch deliberately does not do that.

## Current remote facts, separately from historical experiments

Read-only GitHub tree metadata for growth commit
`0a043b7e7669dad6985c24b19d3c628ab2ee90d9`, cycle **5909**, reports:

| File | Bytes | MiB |
| --- | ---: | ---: |
| `state/organism.json` | 90,905,164 | 86.69 |
| `state/journal.jsonl` | 81,474,312 | 77.70 |

[Growth run 37548936688](https://github.com/JeremyHennessy/AgentTest/actions/runs/37548936688)
succeeded and emitted warnings for both sizes. These are measurements of that
specific commit, not a claim about a later moving branch. No live snapshot or
journal was downloaded or rewritten for this study. The live compact-snapshot
size has not been measured.

[GitHub documents a 100 MiB per-file block](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).
At the pinned commit, the snapshot has 13.31 MiB of headroom and the journal has
22.30 MiB. The formatting correction does not solve unbounded history growth;
no exhaustion date is inferred.

## Historical copied-state evidence

All large-state experiments below use the **historical cycle 4599** checkpoint
from `autonomous/growth@bc4de8cb09aff13db0e123043bee84b38b511d79`, retained from
the Oct 6 validation. They are not cycle-5909 results or natural progress.

- State SHA-256: `276c7e6da74388a330b47390753eb8d9cc18126558712dff149964b85d164471`
- Journal SHA-256: `cdfc2a58430ed9cb46b3979eefdfcd66724e42738b6827f0485b24caa47a7124`
- Original state: 71,520,269 bytes; same decoded data compact: 49,497,171 bytes.
- Original journal: 59,944,566 bytes, 13,799 events. It was never rewritten.

The study compares exact main diagnostic scripts with the two-call candidate.
All `src/agenttest` files are identical between the two roots. Every save,
diagnostic invocation, cache-hit retry, and ordinary copied planning cycle runs
in a new process with a matched fixed clock. No credentials are passed to the
workers; network connects are rejected. Inputs are copied into a new temporary
directory, and source hashes are rechecked afterward.

Fifteen cold-process stages passed, including two ordinary copied planning
cycles, strict grounded experiment admission, both diagnostic cache misses, and
repeated cache hits. The initially retained cycle-4599 diagnostic records were
already cached. Cache hits performed no state or journal writes. Full canonical
state, reloaded state, result/report objects, and the entire journal hash match
at every corresponding stage; no timestamps or other fields are excluded.

| Stage | Existing writers, bytes | Candidate, bytes | Saving |
| --- | ---: | ---: | ---: |
| Cycle 4600, after both diagnostics | 71,534,411 | 49,507,112 | 22,027,299 |
| Cycle 4601, after both diagnostics | 71,548,457 | 49,516,981 | 22,031,476 |

The final copied-state saving is 30.79%. The original 59,944,566 journal bytes
remain an exact prefix in both arms. Two cycle events and four system-diagnostic
events are appended identically, for six new events and 31,467 new bytes.
Following each diagnostic sequence, the next ordinary cycle also produces
identical full state and output under matched observations.

Repository-source changes affect Ora's observed baseline fingerprint. Matched
observations in this preservation experiment do not imply that deployment is
invisible to Ora, or that future natural choices must be identical. Existing
intervention handling must continue to classify the changed source normally.

## Remaining causes, with historical measurements

At cycle 4599 the largest compact value payloads are experiments (11,425,533
bytes, 4,577 rows), system diagnostics (9,740,566 bytes, 9,117 rows), episodes
(5,169,772 bytes, 13,701 rows), predictions (5,052,615 bytes, 4,599 rows), and
intentions (4,886,975 bytes, 4,599 rows). Planning history and temporal world
claims add 4,306,466 and 4,265,688 bytes. Top-level key and punctuation overhead
is not attributed to those value sizes.

The two system-diagnostic context hashes include the current cycle. Therefore
same-cycle replay is cached, while unchanged outcomes in later cycles still
produce distinct evidence records. The historical diagnostic results include
2,239,061 bytes of exact repeated subfield values, but their enclosing records
have distinct identities/provenance. This is a compression opportunity, not
permission to delete evidence. Prediction and experiment records also repeat
templates and linked empirical payloads. Several main histories are append-only;
the 128-entry agenda decision window is already bounded and is not an unlimited
list.

Historical journal cycle events account for 58,028,488 of 59,944,566 raw bytes.
Their largest canonical value contributions are agenda decisions (17,116,498),
inquiry updates (13,787,166), empirical-learning updates (8,034,697), and planning
results (5,546,735). Dropping these fields changes the audit/replay contract.

Gzip of the original historical snapshot produces 2,911,548 bytes and restores
the complete original byte string, including formatting. This is an in-memory
lossless-codec experiment, not a production codec/reader migration. See
`journal-storage-design.md` for the separate sustainability design and gates.

## Validation and reproduction

Nine new focused storage tests pass. The broader diagnostic subset passes
46 tests total. The compactness regression fails against both unmodified main
writers, as expected, and passes after this patch. Coverage includes both
diagnostic kinds, cold-process cache hits and a subsequent copied cycle,
Unicode/escaping, large integers, signed zero, list order, write/replace errors,
partial temporary writes and retry, malformed journal input, source preservation,
and output-alias rejection (including symlinks and hardlinks).

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m unittest discover -s tests -p '*diagnostic*.py' -v

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python scripts/storage_growth_study.py \
  --state /path/to/historical-organism.json \
  --journal /path/to/historical-journal.jsonl \
  --provenance 'HISTORICAL cycle4599, growth@bc4de8cb09aff13db0e123043bee84b38b511d79' \
  --baseline-root /path/to/exact-main \
  --candidate-root /path/to/candidate \
  --cycles 2 --output /path/to/separate-result.json
```

The study does not replace the full suite, baseline-owned behavioral gate,
independent review, or post-merge verification. Existing state-save-before-journal
append behavior remains nontransactional, and temporary-file replacement does
not establish power-loss durability. This patch does not revive closed recovery
PRs 204–208, add infrastructure, rotate history, or activate a new world.
