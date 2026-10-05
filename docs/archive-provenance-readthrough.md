# Archive provenance read-through for real referenced episodes

Status: isolated copied-state research. No production archive/retention activation.

Base: `e3672c473723159232ab494a108eeca7d1903842`.
Pinned state: `autonomous/growth@906d216b54d76e3cb57c540cf59fd57004f29bf3`.

PR #185 already proved immutable archive existence, exact recovery, corruption rejection and separation from generic evidence authority for 1,000 conservatively unreferenced records.

This experiment asks the next question:

> Can a record that **current state still references for historical provenance** live outside the hot episode ledger, remain resolvable by an explicit provenance reader, and still remain unavailable as generic/native/cognition grounding evidence?

## Real referenced records

The study recursively inventories current episode references outside the hot ledger and deterministically selects the earliest record whose references belong only to each of:

1. world-model evidence provenance;
2. semantic-memory episode provenance;
3. Planning Lab memory provenance.

It archives those exact records in the already-proven immutable segment format.

This intentionally crosses the previous conservative rule that protected every explicit reference. It is therefore a separate consumer-integration proof, not an expansion of the archive-eligibility policy.

## Resolver contract

`ArchiveProvenanceResolver` resolves only:

- `historical_lookup`
- `provenance_lookup`

It searches hot records first, then a verified immutable archive segment.

Archive membership does **not** modify `known_evidence_ids()`.

The resolver rejects all attempts to use archived records for:

- generic evidence;
- native inquiry grounding;
- native inquiry resolution;
- cognition grounding;
- self-proposal grounding.

Missing records fail explicitly; hot/archive overlap and duplicate ownership across archive segments fail closed.

## Copied-state acceptance

After moving the three selected referenced records into the external segment:

- all three existing state references remain present;
- all three exact records resolve from the archive for provenance;
- none become generic known evidence;
- the full original ledger reconstructs exactly;
- five ordinary baseline/hot cycles match after expected archive normalization;
- all three references remain present and resolvable after every cycle;
- full ledger reconstruction matches baseline after every cycle;
- source state remains byte-identical.

No production consumer is wired to this resolver in this experiment.

## Interpretation

A pass establishes that referenced historical provenance and evidence authority can be separated in principle on real copied state.

It does not yet authorize physical production pruning. A production archive interface must define which consumers may request provenance and must fail safely when the archive is missing/corrupt.

After this proof, the retention path is sufficiently mature to pause architectural exploration and return the richer 5×5 world to the active queue in shadow/observe-inquire mode while storage compaction/journal rollover remains a separate operational track.

Phase42 remains untouched. Phase43 still waits for a genuine natural evidence-driven suspended-thread resumption.
