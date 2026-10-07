# Recovery and version provenance

V3 is an implementation-snapshot revision. The preregistered protocol stays V4.
The existing [workspace-loss disclosure](../RECOVERY.md) remains unchanged.

The API is the exact 46-file closure from #223 at
`cd74ab1db60bf650cc6730db95a4137d578e49df`, with code-manifest digest
`79596c1a670cfb9cd201e0e163d43924ab98eb00473688f75669f7b8d64a6078`.
Its recovered bytes were verified without imports and are not staged in these
authored tests. The 59-file executed foundation, its original manifest and #224's
compiler portability fix remain immutable.

All 34 scientific Python modules were initially recovered exactly against retained
manifest `890a2a6bb78bb13c152e51f5069d5fecfd58d1baebe86aab282794a2b6901d1d`.
V2 then corrected two modules, scientific transport and reporter. V3 changes only
the controller from v2; 31 of the original recovered Python modules remain
unchanged. The current [module manifest](evidence/entry-fixed-package-manifest-v3.json)
has SHA-256 `2762f7becaaea2e526f0ad6a8dde2df24c8428c16765b9f27ca73b3be88635d1`.
The [v3 source freeze](evidence/entry-fixed-source-freeze-v3.json) records the
one-module before/after hashes. The native C is unchanged.

Five scientific test modules were replayed from retained payloads without a
pre-loss final hash: driver, scorer, scientific controller, scientific transport
and scientific reporter. They are newly verified inputs, not a claim of exact
old final-test recovery. The launcher test did match its retained final hash.
The new v3 regression is a further explicit controller-test change.

The original pre-loss 113-check completion remains unknown. The subsequent
recovery 113-check result, focused v2 checks, unpublished v2 publication's
115-check result and fresh v3 verification have separate identities. The
[v2 verification receipt](evidence/history-v2/publication-verification-v2.json)
and [v2 test log](evidence/history-v2/publication-zero-world-tests-v2.log) are
preserved. The archived v2 signoff is superseded for operational entry correctness
because its controller had the Python `-c` package-context defect. It must not be
used as the current entry-readiness receipt.

The [new v3 disabled build receipt](evidence/new-disabled-build-v3.json) binds
binary `ce8329967b45d5f8c260aaf64578f4ed5669f21baca804ce54444d0c97af137f`.
That binary was compiled but not invoked and is not included. It is distinct from
both the earlier v2 recovery build and the missing old scientific binary
`5950043f1b196842bde7f273431ffd80aba5982d2c2fb144105dc2523667f8f8`.
The recovery profile is referenced by hash, not published as an operational
configuration. Current and historical artifact mappings are in
[publication-provenance-v3.json](evidence/publication-provenance-v3.json).

The completed six-call software fixture preceded the loss. Its exact source and
compact audit survived in #224, but its full raw capsules/ledger, original binary
and original marker remain unavailable. Hashes are not recovered bytes, so the
full old audit cannot be reconstructed from this repository alone. The attempt
remains consumed and must not be rerun after loss. No scientific comparison or
scientific native role was invoked for this publication.
