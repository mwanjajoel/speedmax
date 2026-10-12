---
name: speedmax
description: Performance audit, advice, and approved fixes for web apps, APIs, and AI products in any stack. Use for any question or task about making a page, endpoint, query, or AI feature faster, including quick one-line questions, such as "make it faster", slow pages, Lighthouse or PageSpeed scores, Core Web Vitals (LCP, INP, CLS), lazy-loading, image formats (WebP/AVIF), fonts and preloading, CDN and cache headers, third-party scripts, unused packages, bundle size and code splitting, debouncing search, slow queries, indexes, N+1, pagination, API caching, background jobs, streaming AI responses, loading skeletons, server region, or cold starts. Answers about the user's repo must inspect their code first. Run the complete workflow only for explicit full performance audits, "speed up this app" requests, or requested report artifacts; otherwise answer from the relevant companion file.
---

# Speedmax

Find what makes the product slow for real users, prove it with a number, fix the biggest costs first, and prove each fix with a second number. This is a measure-first workflow. A suggestion with no baseline measurement or concrete source mechanism is not a confirmed finding.

## Operating modes

This skill is guidance by default. Loading it does not authorize the full workflow, file creation, or source edits.

- **Guidance mode**: For focused questions ("why is this page slow?", "should I index this column?", "how do I stream this response?"), use only the relevant companion file. Do not run all phases, create an output directory, or edit code unless the user asks. When the question is asked inside a repository, read the code it is about before answering (read-only: locate the route, component, query, or config with search, then open it) and ground the answer in `file:line` references and what the code actually does. Never answer generically when the code is available; the specific defect in their code is usually the answer.
- **Full audit mode**: When the user explicitly asks for a performance audit, a full or end-to-end speed review, or report artifacts, run Phases 1–4 and write the artifacts defined below. Stop at the approval gate (Phase 5).
- **Fix mode**: Apply only findings the user has approved by ID, then re-measure (Phases 6–7). Fix mode never starts without an approved `findings.json` or an explicit, specific instruction from the user.

If the request could mean more than one mode, ask one focused question before creating files or editing source.

## Platform terminology

This skill is agent-neutral:

- **Parent** is the agent that coordinates the run and owns all shared files.
- **Sub-agent** is the platform's delegation mechanism (Task tool, Agent tool, or equivalent). If none exists, the parent runs each step itself.
- **Core discipline** blocks in the companion files are written to be pasted verbatim into sub-agent prompts.

## Execution safety

These rules apply in every mode.

- **Measure non-production targets.** Measure a local production build (`build` + `start`/`preview`), a preview deployment, or a staging URL the user names. Never load-test, crawl, or repeatedly benchmark a production or shared environment. A small number of Lighthouse runs against a production URL the user names is acceptable.
- **External measurement services need consent.** PageSpeed Insights, WebPageTest, and similar services send the URL to a third party. Ask before using them, and only for URLs that are already public.
- **No surprise installs.** Do not install packages or global tools (Lighthouse CLI, knip, sharp, bundle analyzers, query profilers) without asking. Prefer `npx --yes` one-off runs only after the user agrees, and never add them to the target's dependencies unless that is the approved fix.
- **Databases.** Run `EXPLAIN`/`EXPLAIN ANALYZE` only against a local or disposable database with representative data. Never create indexes, run migrations, or run write queries against a shared, staging, or production database. Deliver index changes as migration files.
- **Secrets and data.** Do not paste environment values, tokens, or customer data into reports. Use row counts and timings, not row contents.
- **Source edits.** In fix mode, work on a new branch (`perf/speedmax-<date>` unless the repository uses another convention), make one logical change per commit, and never force-push or rewrite history.
- **Behavior is the constraint.** A change that alters visible content, accessibility, SEO, data correctness, or security in order to improve a metric is a regression, not a fix.

## Full audit setup

Resolve these values before Phase 1:

- **Skill directory**: the absolute directory containing this `SKILL.md`.
- **Target**: the absolute repository root under review.
- **Repo name**: from the directory name or Git remote.
- **Output directory**: a new directory outside the target, defaulting to `~/speedmax-audits/<repo-name>/run-<N>` where `<N>` is the next unused integer. Use a directory inside the target only if the user chooses it and version control ignores it.
- **Measurement target**: the local command or URL that will be measured, the routes to measure (default: home plus the 2–4 most important routes from reconnaissance), and the device profile (default: Lighthouse mobile).
- **Prior runs**: if earlier runs exist for this repo, read their `findings.json` and `baseline.json` so the report can show trend and avoid re-proposing rejected items.

The parent is the only writer of these run files:

- `run-metadata.json` — repo, target, source ref (commit + dirty flag), measurement target, routes, profile, date, `run_status`
- `baseline.json` — raw metrics from Phase 1
- `ledger.json` — per-check applicability from Phase 2
- `findings.json` — validated findings from Phases 3–7
- `REPORT.md` — the human report
- `after.json` — post-fix metrics (fix mode only)

Validate before reporting:

```bash
node <skill-dir>/validate-findings.cjs <output-dir>/findings.json <output-dir>/ledger.json
```

## Core principles

### Measure first

Every audit starts with a baseline. Without one, the user cannot tell which fix mattered and the agent cannot rank them. Use the median of 3–5 runs; one Lighthouse run is noise.

### Require a mechanism and a number

For every candidate, name: the route or endpoint affected, the user-visible metric it moves (LCP, INP, CLS, TTFB, FCP, transfer bytes, p95 latency, query count, time to first token), the source location that causes it, and either a measured value or a source-grounded estimate clearly labeled as an estimate. Checklist deviations with no measurable cost are not findings.

### Biggest user-visible cost first

Rank by impact on real users of the most important routes, then by effort. A 1.5 s LCP win on the landing page beats a 40 KB saving on an admin page.

### Respect what is out of source

CDN configuration, hosting region, instance minimums, database size, and real traffic patterns are often not visible in the repository. Do not guess. Record `needs_measurement` with the exact missing fact and how the owner can check it. The test: if the sentence that makes the finding true contains a hedge about an unseen fact ("I believe", "probably", "likely", "by default the host…", "not verified"), the verdict is `needs_measurement`, not `confirmed`.

### Smallest effective fix, then prove it

Prefer the narrowest change that removes the cost: a missing `loading="lazy"`, one eager-load, one index, one dynamic import. Re-measure after each fix. If a fix does not move its metric, revert it and record `reverted`.

## Impact calibration

Only `confirmed` findings receive impact. Thresholds are the "good / needs improvement / poor" bands from Google's Core Web Vitals (mobile, 75th percentile) plus backend equivalents:

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP | ≤ 2.5 s | ≤ 4.0 s | > 4.0 s |
| INP (lab proxy: TBT) | ≤ 200 ms (TBT ≤ 200 ms) | ≤ 500 ms (TBT ≤ 600 ms) | > 500 ms (TBT > 600 ms) |
| CLS | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| TTFB | ≤ 0.8 s | ≤ 1.8 s | > 1.8 s |
| FCP | ≤ 1.8 s | ≤ 3.0 s | > 3.0 s |
| API p95 | ≤ 300 ms | ≤ 1 s | > 1 s |
| AI time to first visible token | ≤ 1 s | ≤ 3 s | > 3 s |

- **high** — on a main route or main API, the issue alone moves a metric across a band boundary (for example LCP from good to poor), or causes work that grows with data size (N+1, unpaginated lists, missing index on a growing table), or a cold start adds more than 1 s to a main route.
- **medium** — the issue moves a metric within the "needs improvement" band, or the impact is high but limited to a secondary route.
- **low** — a marginal saving (small bytes or milliseconds) with no band change.

Each confirmed finding also records **effort**: `S` (under an hour, local change), `M` (a day or less, touches several files), `L` (architecture, infrastructure, or data migration). The priority order in the report is impact descending, then effort ascending.

## Workflow

### Phase 1 — Measure the baseline

Follow [MEASUREMENT.md](MEASUREMENT.md). Build and serve the target locally (or use the agreed URL), run Lighthouse mobile 3–5 times per route, and record backend timings where available. Write `baseline.json`. If the target cannot be built or served, record why in `run-metadata.json`, continue with static analysis, and mark every metric-dependent check `needs_measurement`.

### Phase 2 — Reconnaissance and coverage ledger

Follow [RECONNAISSANCE.md](RECONNAISSANCE.md). Detect the stack, routes, data layer, AI calls, hosting, and third parties. Write `ledger.json` with every check ID marked `applicable`, `not_applicable`, or `blocked`, each with a reason. No check may be silently skipped.

### Phase 3 — Check every applicable item

For each `applicable` check, follow its entry in the companion files:

| Check IDs | Companion file |
|---|---|
| MEAS-01 | [MEASUREMENT.md](MEASUREMENT.md) |
| IMG-01, IMG-02, CDN-01, FONT-01, 3P-01 | [FRONTEND-ASSETS.md](FRONTEND-ASSETS.md) |
| DEP-01, JS-01, UX-03 | [JAVASCRIPT-AND-BUNDLES.md](JAVASCRIPT-AND-BUNDLES.md) |
| DB-01, DB-02, DB-03, CACHE-01, JOB-01 | [DATA-AND-BACKEND.md](DATA-AND-BACKEND.md) |
| UX-01, UX-02 | [PERCEIVED-PERFORMANCE.md](PERCEIVED-PERFORMANCE.md) |
| INFRA-01, INFRA-02 | [INFRASTRUCTURE.md](INFRASTRUCTURE.md) |

On large targets, delegate one sub-agent per companion file in parallel, pasting that file's Core discipline block into its prompt. Sub-agents return structured candidates; they do not write shared files or edit source.

### Phase 4 — Report and prioritize

Consolidate candidates, deduplicate by root cause, assign impact and effort, and write `findings.json` and `REPORT.md` per [REPORTING.md](REPORTING.md). Run the validator. Every finding starts with `status: "proposed"`.

### Phase 5 — Approval gate

Present the prioritized list to the user: ID, one-line title, impact, effort, and expected metric change. Ask which findings to apply. Record approvals by setting `status: "approved"`. Stop here unless the user approves at least one finding. Never treat silence or a general "looks good" as approval for `L`-effort or infrastructure findings; confirm those individually.

### Phase 6 — Apply approved fixes

Follow [FIXING-AND-VERIFICATION.md](FIXING-AND-VERIFICATION.md). Work in priority order on a branch, one finding per commit, running the project's existing tests and build after each change. Set `status: "applied"`.

### Phase 7 — Re-measure and final report

Repeat the Phase 1 measurement with the same routes, profile, and run count. Write `after.json`, record each finding's `after` value, set `verified` or `reverted`, re-run the validator, and update `REPORT.md` with a before/after table.

Do not end a full audit before one of two terminal states: (a) `REPORT.md` is written and the validator passes, or (b) `run_status: "incomplete"` is recorded in `run-metadata.json` with the exact reason, and the report says what was not covered.

## Anti-patterns

1. Recommending fixes before measuring.
2. Reporting from a single noisy Lighthouse run, or comparing runs with different throttling, device, or build mode (dev vs production).
3. Lazy-loading the LCP image or anything above the fold.
4. Adding a cache without stating what invalidates it and how stale data may be.
5. Adding indexes on columns no query filters, joins, or sorts by, or on tiny tables.
6. Removing a package that is only imported dynamically, through config, by a CLI script, or as a peer dependency.
7. Splitting code so finely that the critical path makes more round trips than before.
8. Adding a CDN or edge layer on top of one already provided by the host.
9. "Fixing" a score by hiding content, deferring the main content, or user-agent sniffing Lighthouse.
10. Moving work to a background job when the user needs the result in the same response.
11. Keeping a fix that did not move its metric.
12. Measuring a development build.
