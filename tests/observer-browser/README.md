# Synthetic Observer browser checks

These tests render the exact checked-out `index.html` in Chromium at desktop
1440×900, mobile 390×844 and narrow landscape 844×390. All state is the small
synthetic `fixture.json`; screenshots do **not** depict live Ora state.

Every browser request is intercepted before the page loads. Only the synthetic
page, growth ref and immutable snapshot URLs are fulfilled. Other requests and
all write methods are blocked and fail the test. The owner handoff uses a stubbed
`window.open`, so no GitHub interaction or popup is sent. There are no secrets,
external models, live organism downloads or production state changes.

Run from this directory with Node 20 or later:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npx --no-install playwright install --with-deps chromium
OBSERVER_EXPECTED_HEAD_SHA=$(git rev-parse HEAD) npm test
```

`npm run list` discovers the 24 browser cases without launching Chromium.
`npm run test:unit` runs the existing 23 transport/DOM model tests. Browser
execution requires a functioning ordinary Chromium environment; do not weaken
security restrictions to force a blocked local launch.

Browser coverage includes viewport overflow, map/trails/plan/learning, expanded
evidence, keyboard skip and focus, disclosures and labelled owner input, manual
and periodic refresh overlap, unchanged-source download reuse, abandoned response
ordering, HTTP errors, whole-view preservation after malformed nested data,
accepted-state age ticks, late renderer failure and recovery, and first-load
unavailability.

Artifacts are ignored under `.artifacts/`: PNGs, the HTML/JSON report, failure
traces and per-test manifests recording the actual Git head, expected head,
original HTML and fixture SHA256, viewport, browser/tool versions, result and
intercepted request log. Screenshot attachments are review evidence, not approved
visual baselines. Inspect them before closing the rendered QA gate.

`verify-job.snippet.yml` prepares the focused job for later integration into
`verify.yml`. It is a reference file, not an executable workflow. Publishing a
workflow modification is currently blocked by automatic approval review because
the original task prohibited workflow changes. Direct user approval is required
for that separate integration. The existing Python verification jobs and all
runtime/deployment workflows are unchanged. GitHub runner assignment may queue
during its reported incident; do not repeatedly dispatch or rerun jobs. Parent
coordinates exact-head verification and final review.
