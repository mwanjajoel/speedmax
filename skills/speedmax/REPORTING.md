# Reporting

#### When to use this file

Use this file in Phase 4 (and again in Phase 7) to write `findings.json` and `REPORT.md`. The JSON is the source of truth; the report is derived from it and must not disagree with it.

## `findings.json`

An array of finding objects. The full contract is `findings-schema.json`; the validator enforces it:

```bash
node <skill-dir>/validate-findings.cjs <output-dir>/findings.json <output-dir>/ledger.json
```

```json
[
  {
    "id": "F-001",
    "check_id": "IMG-02",
    "title": "Hero image on / is lazy-loaded, delaying LCP",
    "verdict": "confirmed",
    "impact": "high",
    "effort": "S",
    "routes": ["/"],
    "locations": ["app/page.tsx:14"],
    "mechanism": "next/image without priority; LCP element is img.hero and it waits for layout before loading.",
    "evidence": { "tool": "lighthouse", "metric": "lcp_ms", "baseline": 4810, "unit": "ms", "runs": 5 },
    "fix": { "summary": "Add priority to the hero <Image> and set sizes=\"100vw\".", "files": ["app/page.tsx"] },
    "expected": "LCP below 3.0 s on mobile",
    "status": "proposed"
  },
  {
    "id": "F-002",
    "check_id": "INFRA-02",
    "title": "Main API may cold start on Cloud Run",
    "verdict": "needs_measurement",
    "routes": ["/api/products"],
    "locations": ["deploy/cloudrun.yaml:12"],
    "mechanism": "minScale is 0 and the handler imports the full AWS SDK at module load.",
    "missing": "First-request latency after 15 min idle on a preview deployment.",
    "status": "proposed"
  }
]
```

Field rules:

- `id`: `F-` plus three or more digits, unique.
- `check_id`: one of the 18 check IDs.
- `verdict`:
  - `confirmed`: there is a measured number, or a source-grounded mechanism with a stated estimate. Requires `impact`, `effort`, `evidence`, and `fix`.
  - `needs_measurement`: the mechanism is in source but the deciding fact is not available. Requires `missing`. Must not have `impact`. Use it whenever the finding depends on host, CDN, browser, or data-size behavior you did not observe, even if you think you know the default.
  - `not_applicable`: rarely needed in findings (the ledger records applicability); use it only to explain a notable non-issue.
- `evidence.baseline` is a number from the baseline, or `null` with `evidence.estimate` explaining a source-grounded estimate (for example "51 queries per request for 50 rows, grows with N").
- `status`: `proposed` → `approved` → `applied` → `verified` or `reverted`. `verified` and `reverted` require `after` with the same `metric` as `evidence`.

## `REPORT.md` layout

1. **Summary**: three sentences: overall state (score and Core Web Vitals per main route), the top three wins, and coverage limits.
2. **Baseline**: a table per main route with median LCP, TBT, CLS, FCP, TTFB, bytes, and score; backend and AI timings.
3. **Prioritized findings**: one table ordered by impact then effort (`ID | Check | Title | Impact | Effort | Expected change`), then one short section per finding with mechanism, locations, evidence, and fix.
4. **Needs measurement**: each item with the exact missing fact and how the owner can get it.
5. **Coverage**: the ledger summary: applicable, not applicable (with reasons), blocked (with the missing fact).
6. **Before/after** (Phase 7 only): per-route metric deltas and per-finding status.

Write plainly. Lead with numbers. Do not include secrets, environment values, or customer data.
