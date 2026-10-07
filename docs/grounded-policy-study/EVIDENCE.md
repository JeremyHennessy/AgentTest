# Evidence provenance and field annotations

The included receipts are archival copies or explicitly labeled byte excerpts.
They are never executable approval. `evidence/source-map.json` maps published
paths to original files. `evidence/preserved-artifact-inventory.json` records
SHA-256 and length for omitted raw files, the one-attempt marker, reviewed build,
pre-execution handoff and operational receipt. Those originals remain unchanged.

## Exact reviewed inputs

The full documents are in the
[reviewed-inputs archive](../../experiments/grounded_policy_study/executed_snapshot/reviewed-inputs/).

| Input | SHA-256 |
| --- | --- |
| FIRST_COMPARISON_V4.md | `0764aab03b99d59cc9eeb9c3aaeac481beda5c955c860e6c3db5f94fd08bda50` |
| AMENDMENT_RECORD.md | `095db08770dcd89a358abcad80562b027abf58c09e23fb8aa9376141f966d80a` |
| PROTOCOL_V4_EXACT_BYTE_SIGNOFF.md | `d33be2c89ed7e1563f872574d4b7186d31e9507977284dac9c8eacc70471e0dd` |
| PROTOCOL_COHORT_CONSTRUCTION_AMENDMENT_REVIEW_V2.md | `7c0be59220df4b44d578c2a48c4859ba9db647712c768ff89e7701017d6e282f` |
| Completed native fixture audit | `d9d3d82bc9be308e036a26f3450ccfc75c83671c921c5b2b5b9c74286be90f4a` |
| Executed 59-file manifest | `44501db2a928139f0131956f492818d92854c70a7b068eb19169ef795e09f956` |

The original comparison protocol remains archived in the snapshot and the
unchanged base. V4 is prospective; protocol signoff does not activate a study.
The pre-execution source freeze retains its original 59-file source digest
`34ba5cb0a84158b07d2bf30d7f9c1829b5c22bc712a8bf3f7f5e6f78c74f0f5a`.
The separate runtime-package manifest digest is
`312911c5a35368182b650003f89ff247861948bf9f1ed65d30d5f15d6f11e6ff`.

## Historical wording and raw metadata

The executed snapshot README says the bounded fixture is pending, and some
source comments describe pre-review disabled guards. Those texts predate the
completed run. They are retained to preserve the executed snapshot. The actual
source assignments, historical enabling diff, terminal evidence and independent
audit establish the later narrow fixture result. The current status is recorded
in [IMPLEMENTATION.md](IMPLEMENTATION.md).

The raw terminal field `authored_null_decisions = 4` counts completed decisions
in native-fixture mode. It does not mean four nulls: the saved decisions and audit
establish **zero null decisions**. `stub_workers_observed_started = 14` includes
the native cold dispatches. `stub_reporters_observed_started = 0` and the unused
reporter PID/affinity fields describe the native reporter-specific role; the
saved-JSON reporter ran as a generic cold worker and is present in the ledger.
The generic `actual_api_invocations = null` does not override exact per-function
and per-worker counters.

The compile-only builder emitted `controller_role = pending_native_fixture` and
`native_fixture_admission_reviewed = false` in its build receipt. That receipt
records build preparation and never created a GO receipt. The separately
reviewed enabling changes and executed terminal receipt show the narrow fixture
admission as true. Preserve both records; do not edit the build metadata into a
post-execution approval claim. Scientific execution remains false throughout.

`terminal-status-excerpt.json` contains the exact occupied bytes of the final
reserved slot at offset 65,536 in the original `launcher.status`; padding is not
included. The inventory binds both this excerpt and the full original file.
`fixture-candidate-report.json`, the independent audit, build/profile/package
receipts, and pre-execution freeze are byte-for-byte copies. Derived publication
verification is stored separately and never replaces the original evidence.

The full raw data and compiled binary were verified locally before the cloud
workspace became unavailable during session recovery. Those omitted bytes are
currently unavailable; their hashes cannot reconstruct them. Retained source and
compact receipts were recovered exactly. See [RECOVERY.md](RECOVERY.md) and
[LIMITS.md](LIMITS.md).
