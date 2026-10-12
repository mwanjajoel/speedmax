# Fixing and Verification

#### When to use this file

Use this file in fix mode (Phases 5–7): after `findings.json` exists and the user has approved specific findings. It defines the approval gate, how to apply fixes safely, how to prove them, and how to keep them from regressing.

## Core discipline (include in every agent prompt for this domain)

```
- Apply only findings with status "approved". Never widen scope; note new issues as new proposed findings instead.
- Work on a branch. One finding per commit, with the finding ID in the commit message.
- After each fix, run the project's existing build, typecheck, lint, and tests. A fix that breaks them is reverted, not patched around.
- Re-measure with the same procedure as the baseline. Keep a fix only if its metric improved; otherwise revert it and mark it "reverted" with the numbers.
- Never apply migrations, infrastructure changes, or package installs to shared or production environments.
```

## Phase 5 — Approval gate

Present the findings as a short table in priority order:

| ID | Check | Title | Impact | Effort | Expected change |
|---|---|---|---|---|---|
| F-001 | IMG-02 | Hero image is lazy-loaded on `/` | high | S | LCP −1.2 s |

Then ask: "Which findings should I apply? (for example: all S-effort, or F-001, F-003)". Rules:

- "All", "all S", or a list of IDs counts as approval for those IDs.
- `L`-effort findings and anything in `INFRA-*`, database migrations, removing third-party scripts, or changing a public API response shape need individual confirmation, even when the user says "all".
- Record approvals by setting `status: "approved"` in `findings.json`. Unapproved findings stay `proposed`.

## Phase 6 — Apply

1. Create a branch: `git switch -c perf/speedmax-<yyyy-mm-dd>` (or the repository's convention). If the worktree is dirty, stop and ask.
2. For each approved finding in priority order:
   1. Make the smallest change described in the finding's `fix`.
   2. Run build, typecheck, lint, and tests using the commands found during reconnaissance.
   3. Commit: `perf(<area>): <title> [speedmax F-001]`.
   4. Set `status: "applied"`.
3. If a fix needs a new dependency, ask before installing it, even if the finding was approved.
4. Database index fixes produce a migration file only. Tell the user how to apply it safely (for example `CREATE INDEX CONCURRENTLY` in a low-traffic window).
5. Infrastructure fixes produce a config change and a short note with the cost. Do not deploy.

## Phase 7 — Re-measure and verify

1. Rebuild and repeat MEASUREMENT.md exactly: same routes, profile, run count, and build mode. Write `after.json`.
2. For each applied finding, fill `after` with the metric named in its `evidence` and the new median value.
3. Mark `verified` when the metric improved beyond run-to-run noise (rule of thumb: more than 5% or more than the spread between baseline runs). Otherwise revert the commit (`git revert`), set `status: "reverted"`, and keep the numbers in the record.
4. For backend findings, repeat the same query-count, EXPLAIN, or latency check used as evidence.
5. Re-run the validator and update `REPORT.md` with a before/after table per route.

## Regression guards (recommend, apply only if approved)

- **Lighthouse CI** with budgets (`lighthouserc.json`: `largest-contentful-paint` ≤ 2500, `cumulative-layout-shift` ≤ 0.1, `total-blocking-time` ≤ 200, `resource-summary:script:size` limit) run on pull requests.
- **Bundle size budgets**: `size-limit`, Next.js bundle analysis in CI, or `bundlewatch`.
- **Query count tests**: `assertNumQueries` (Django), `strict_loading`/`bullet` in test env (Rails), `Model::preventLazyLoading()` in non-production (Laravel), a query-count assertion in Node integration tests.
- **Real-user monitoring**: `web-vitals` library reporting to existing analytics, so field data replaces guesses next time.
