# Implementation v3 independent default-off review

Decision: PASS for this exact default-off implementation checkpoint. This supersedes the v2 operational-readiness conclusion and the subsequent embedded-namespace hold. The scientific protocol remains the unchanged preregistered V4. No scientific execution or activation is admitted by this review.

## Final entry correction and verification

The v2 native binary executes captured controller bytes with `python -I -S -B -c`, leaving `__package__` as None. Its embedded main called local helper definitions containing relative imports. The independent reproduction established ImportError in claim_started_marker, failure_status and emit_native_terminal before substantive helper work.

Implementation v3 changes only the controller's existing import from the pinned package module: main now locally binds those three helpers alongside BoundController and reserve_all. An AST comparison against the controller embedded in the v2 binary found no other executable change. The new binary contains the exact new controller bytes and matching package-manifest, profile, package-root, interpreter and output-path bindings. All 34 current module hashes match its manifest; the 46 frozen API sources, native C and Python/numerical runtime bytes remain unchanged.

The regression runs in an actual isolated Python `-c` child with `__name__ == '__main__'` and `__package__ is None`. It asserts the three original global helper ImportErrors, extracts the exact ImportFrom node from main, executes that node inside an authored local scope, and checks the resulting helpers are package-bound and work. The marker-reading helper is stopped by an authored sentinel. API/world imports are blocked. This is an embedded helper-binding regression: neither real main nor the scientific native role was invoked, and no GO receipt or marker I/O occurred.

Verified regression evidence:

- Original failure log: `policy-study-results/v3-helper-reproduction-before.log`, SHA-256 `16e8533799bfd0a3e7d0de36336535e4761632a187b48cde0e03754a14487827`.
- Final regression log: `policy-study-results/v3-helper-regression-final.log`, SHA-256 `2f6b7018bedeb6e41e270bbaf184996fe9664a25aa35a818967bc5078b517b67`.
- Final test source: `662f102b21aaa300488b3bfb74b603677296cdfdb088f26149c8428d32d098ce`.

The earlier `v3-helper-regression-after.log` is an intermediate result and is not the final log above. The recovery baseline had a verified fresh 113-check pass. Three subsequent authored checks covered exceptional native child completion and invalid-report precedence. No broad suite was rerun by this reviewer. Any later packaged-suite result is separate evidence.

## Exact implementation checkpoint

- Source freeze: `5259f8b9263827da5028481b13043c10893b576929f2d379ef9bdf2455dba66b`.
- Package manifest: `2762f7becaaea2e526f0ad6a8dde2df24c8428c16765b9f27ca73b3be88635d1`.
- Controller: `965e94b33025aa7f1d457f6119f2c6eed610bf7a15c9272222cc5d24bdc5e053`.
- Native C: `02d3c429c631d9ec26b25ed16dfd421d48530e4e00a9d5cb0285fa0982e19969`.
- Static disabled binary: `ce8329967b45d5f8c260aaf64578f4ed5669f21baca804ce54444d0c97af137f`.
- Build receipt: `8c9269c35859c26003c2af12aed9f7b9f7d3db3fe6f71934879f7c81f63ffae2`.
- Recovery profile: `bfcd79fce08f39608f3339cc4ab72f3530f0b2ffd0d1f309fc197ace71f9e10e`.

The binary has no ELF INTERP header and was not invoked by this reviewer. The original pre-loss binary remains missing, and completion of the original pre-loss 113-check run remains unknown. These recovery artifacts do not replace that history or grant a rerun of the consumed six-call fixture.

## Unchanged scientific and resource review

The reviewed pipeline keeps the fixed four neutral horizons, 32 paired anchors, 64 unique authorities, 128 decisions and at most 512 transition invocations. Complete D frames and their movement-only projection are independently bound; each cohort matches its layout's first declared real reference before its own T1. Paired first semantics and lifecycle match, and both second T1s plus F/world commitment precede independent common probes. The explicit E1-only retained/withheld view and complete first-null equality are checked against original capsules. The saved scorer independently binds ledger chronology, actual counts, native receipts, masks, denominators and frozen classification rules.

The native source preserves one allowed CPU, the absolute 850-second internal window, the 32/96/384 MiB AS chain, sequential children, parent-death handling and group cleanup. This remains within the unchanged 900 CPU-second, 1,500 wall-second, 512 MiB concurrent RSS and 192 MiB output ceilings, including a separate 1 MiB finalization reserve. The maximum is 422 children and 1,280 native event lines. Canonical ledger segments total at most 17 MiB; reports use fixed bounded chunks. Every temporary/input/log/marker/report slot is reserved. No retry, replacement case, reset or quota replenishment is admitted.

The prior resource-failure fixes remain present: exactly one phase-3 completion follows child reap; zero-allowance reporter uncertainty preserves exact scientific counts; observed illegal calls remain counted; and established invalid results dominate later persistence, reconstruction, cleanup and finalization failures. Native completion also requires consistent full-run counts and successful actual outer exit. A prepared-before-exit receipt alone is insufficient.

These are trusted-source and ordinary Linux kernel/process guarantees, not strict real-time or machine-power-loss guarantees. Authored tests do not establish scientific feasibility, predictive benefit or a scientific denominator.

## Explicit remaining enabling-only gates

All scientific guards remain false, the native reviewed-profile hash remains blank, and the prospective output root, GO receipt and permanent scientific marker are absent. There is no remaining identified implementation blocker for publishing this default-off checkpoint.

Before any scientific run, a separate instruction and exact-byte decision must bind the operational profile, the minimal enabling-only source diff, the rebuilt native binary and full source manifest, and the fixed one-attempt/output/GO paths. Admission must remain for one bounded run only. The completed software fixture stays consumed; no real fixture or scientific replay is granted. This review performed zero API/world/science calls and no activation.
