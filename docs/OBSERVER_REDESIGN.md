# Observer redesign — independent presentation work

Jeremy explicitly requested a redesigned Observer on October 7, 2026 at 23:28:03Z.

The runtime correction in PR #245 remains unpublished and unmerged: a fresh attempt through the same code-write action was blocked. This presentation work does not retry that correction through another route, alter an action controller, or remove the merge hold.

## Baseline and deployment contract

Preserve `index.html` at the main checkpoint `2d9ac236d7bc4e487df13efffe964a081ad8f3c9`, Git blob `f72df3ce6ec3e5be24eadb24764ba1864acc4e03`. The existing source is not rewritten. The Pages artifact will copy it to `legacy.html`, retaining the full old evidence and interaction console. The new `observer.html` becomes the built homepage. Existing page tests continue to protect the legacy source; separate new tests must protect the actual new served page. This is explicit routing, not a claim that testing the old page verifies the new one.

## New presentation

The development and original-live views are separate. The development map is a fixed, sourced receipt of the initial eight-cycle copied test at `58e79e4a15566d4e20c807f78e67e7709fdca192`, not a live pilot. It distinguishes the two learner choices, five planner transitions, and one non-action cycle. Action details retain actual memory IDs and unchanged interrupted-plan step numbers. The goal-arrival correction remains visibly blocked until current repository status supplies newer information; an advanced head cannot inherit the old passing test.

Decision Study 001 is presented with both its modest 13/16 predictive advantage over uniform selection and the repeated-block/temporal-null limitations. No phase success, general-intelligence result, autonomous timing, or live learning is inferred from that study.

The live overview reads only the small original heartbeat receipt. Missing data stays unavailable. Aging or failed reads are explicitly labeled without claiming the organism stopped. The optional map loads the large organism snapshot only on an explicit click, first resolving the growth branch to one exact commit. All map and plan fields come from that commit; a newer heartbeat cannot relabel an older map. Completed historical goals are not substituted for missing active goals.

Only GET requests are used. API reads are limited to five-minute intervals, receipt polling to one minute, and polling pauses while the browser tab is hidden. There are no credentials, new model services, mutations, or workflow dispatches in the page.

## Verification and limits

Local Chromium/Playwright checks cover the rendered page at widths 320, 390, 620, 768, 1024 and 1440 pixels, keyboard tabs, cell/action selection, ownership labels, exact-commit optional map reads, no automatic heavy snapshot read, absent active goals, changed PR heads, future source timestamps, cold failures and retained stale data. Initial local result: 35 checks passed and zero page exceptions. Eight additional structural/syntax tests pass. Network replies are captured GitHub fields or explicitly authored schema/error fixtures, not a live-site visual verification.

The live public page and raw-file download were not reachable from this execution environment. The old page was reviewed through its actual source; no fresh old-page screenshot is claimed. The new screenshots are local renders of the implemented page. A successful Pages deployment must be established separately before calling the redesign published.

No growth, interaction, reconciliation, controller, learner, original state or world file changes belong to this presentation increment. Conservative exploration timing and the persistent Ora 2 pilot remain blocked behind the corrected owned-cycle integration. The broader repository semantic audit remains incomplete.


## October 8, 2026 — dual Pages deployment correction (supersedes routing above)

The original routing contract above was insufficient for the repository's actual GitHub Pages configuration. The custom Actions workflow deployed `observer.html` as the root, but GitHub's separate branch-source `pages build and deployment` ran afterward and served the repository-root `index.html` (old console). The independent hosted read-only check `37839662583` proved the mismatch: the public root served the old 109,346-byte console, the new CSS and JS were available, and `legacy.html` returned HTTP 404. Both deployment workflows reported success; deployment success alone did not verify the intended homepage.

Corrected contract:
- `legacy.html` is an **exact Git blob copy** of the original approved `index.html`, SHA `f72df3ce6ec3e5be24eadb24764ba1864acc4e03`. Original history, UI and interaction behavior remain preserved.
- `index.html` and `observer.html` are **byte-identical** new Observer entry points, Git blob `ff469ade0628d4565b073a3ed0758b8665fed865`, enforced by `cmp index.html observer.html` in CI.
- `pages.yml` copies canonical `index.html` to `_site/index.html`, `observer.html` to `_site/observer.html`, and `legacy.html` to `_site/legacy.html`. Both Pages deployment paths therefore publish the same homepage and preserve the same legacy console.
- Original growth-console tests now read `legacy.html`; new Observer tests read `observer.html` and verify `index.html` parity. No `src/`, `state/`, heartbeat, history or Ora2 runtime changes are involved.

Rollback: original console blob `f72df3ce6ec3e5be24eadb24764ba1864acc4e03`; new Observer source from PR #260 merge `dc73eb02b026d9eca79be390247c97d454e0890e`. After merging this routing repair, verify actual public HTTP bytes for root, CSS, JS and legacy page; do not infer live correctness from Pages green alone.
