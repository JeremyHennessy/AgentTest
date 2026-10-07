# Scientific implementation snapshot v3 (protocol V4)

V3 identifies the implementation snapshot. The preregistered study protocol
remains V4, with unchanged conditions, budgets and acceptance criteria.

This immutable source overlay adds the corrected scientific controller,
transport, saved reporter and scorer on top of #224 at
`f67d9fe7904636949cf1c7cc29a8a4e47beccc37`. Scientific execution has never run
and remains disabled. The independent review passes this default-off checkpoint
only; it grants no execution or activation.

`overlay/` contains exactly nine changed/new runtime files and six changed/new
test files. `SOURCE_MANIFEST.json` describes their composition with the existing
`../executed_snapshot/`. No historical snapshot, API file, protocol, workflow or
existing publication file is modified. The v3 correction binds the embedded Python entry helper calls to the pinned
package module, avoiding relative-import failure when `__package__` is None.
The unpublished v2 signoff is superseded for operational entry correctness.
The resulting runtime has the exact 34
Python modules and native C bytes in the final reviewed v3 implementation freeze.

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -W error::ResourceWarning -m unittest discover -s tests -p 'test_grounded_policy_scientific_extension.py' -v
```

Or run the same isolated entry directly:

```sh
python -I -S -B -W error::ResourceWarning experiments/grounded_policy_study/scientific_extension_v2/run_zero_world_tests.py
```

The runner verifies both source layers and stages exact bytes in a temporary
workspace. It runs 116 selected authored-data checks, without invoking #224's
150-test foundation suite. It reuses the pinned #224 test-only compiler wrapper
and its `-s` link-time flag. Linux and an installed C compiler with static linking
support are required. Source paths and test staging are handled by the new runner;
reviewed runtime and test bytes are unchanged.

The native checks compile a disabled scientific binding without executing it and
run a separate pure C receipt-helper harness. They do not invoke the scientific
native role. No API source, operational profile, GO receipt, started marker, raw
scientific result or historical binary is staged. The six-call software fixture
remains consumed despite the missing original raw evidence and marker.

See [scope and limits](../../../docs/grounded-policy-study/scientific-extension-v3/README.md),
[verification](../../../docs/grounded-policy-study/scientific-extension-v3/VERIFICATION.md),
and [recovery provenance](../../../docs/grounded-policy-study/scientific-extension-v3/PROVENANCE.md).
