# speedmax

**A performance audit skill for AI coding agents.** It works on any codebase. It measures first, reports what actually makes your app slow, and fixes only what you approve. After each fix it re-measures to prove the fix helped.

speedmax is a set of Markdown instructions plus a small validator. Drop it into Claude Code, or any agent that can read a skill file, and ask your agent to make your app faster.

- **Measure first.** No finding without a number or a concrete mechanism in your code.
- **Biggest wins first.** Findings are ranked by user-visible impact, then effort.
- **You stay in control.** No code changes until you approve findings by ID.
- **Proven fixes.** Every fix is re-measured; fixes that don't help are reverted.
- **Any stack.** Recipes for Next.js, React/Vite, Nuxt, SvelteKit, Astro, Rails, Django, Laravel, Express/Prisma, and plain HTML.

---

## Contents

- [What it checks](#what-it-checks)
- [Install](#install)
- [Use it](#use-it)
- [How a full audit works](#how-a-full-audit-works)
- [What you get](#what-you-get)
- [Safety rules](#safety-rules)
- [Evaluation](#evaluation)
- [Repository layout](#repository-layout)
- [Contributing](#contributing)
- [License](#license)

---

## What it checks

speedmax runs 18 checks. Each has a stable ID that appears in the report.

| Area | ID | Check |
|---|---|---|
| Measurement | `MEAS-01` | Run Lighthouse and PageSpeed on mobile (median of 3–5 runs) |
| Images | `IMG-01` | Compress images to WebP or AVIF, sized correctly |
| | `IMG-02` | Lazy-load images below the fold, but never the main (LCP) image |
| Delivery | `CDN-01` | Serve static files from a CDN with long-lived cache headers |
| Fonts | `FONT-01` | Preload the main font, and use only 1–2 font families |
| Third parties | `3P-01` | Remove third-party scripts you don't need; defer the rest |
| JavaScript | `DEP-01` | Remove packages that were added but never used |
| | `JS-01` | Split JavaScript so each page loads only what it needs |
| | `UX-03` | Debounce search inputs and cancel stale requests |
| Database | `DB-01` | Add indexes on columns you filter, join, or sort by |
| | `DB-02` | Fix N+1 queries |
| | `DB-03` | Paginate lists instead of loading everything |
| Backend | `CACHE-01` | Cache API responses that rarely change, with a clear invalidation rule |
| | `JOB-01` | Move heavy work (email, images, exports) to background jobs |
| Perceived speed | `UX-01` | Stream AI responses instead of waiting for the full answer |
| | `UX-02` | Show skeletons and loading states, not blank screens |
| Infrastructure | `INFRA-01` | Put your server close to your users and your database |
| | `INFRA-02` | Remove cold starts on your main routes |

Every check has the same sections in its companion file:

- **Why it matters**: which metric it moves.
- **Detect**: commands and code patterns to look for.
- **Evidence required**.
- **Fix**: per-framework recipes.
- **Verify**: how to show it worked.
- **Pitfalls**: common mistakes to avoid.

---

## Install

### Claude Code

For all your projects:

```bash
git clone https://github.com/mwanjajoel/speedmax ~/.claude/skills/speedmax
```

For one project only (it can be committed with the project):

```bash
git clone https://github.com/mwanjajoel/speedmax .claude/skills/speedmax
```

Claude Code picks up the skill automatically the next time it starts.

### Other agents

Point your agent at `SKILL.md` as its instructions, for example from `AGENTS.md`, a system prompt, or your tool's rules file. `SKILL.md` links to the companion files and tells the agent when to read each one.

### Requirements

- **Validator:** Node.js 18 or later.
- **Real measurements:** Chrome and Lighthouse (`npx lighthouse`). The agent asks before installing or running anything.

---

## Use it

speedmax has three modes. The agent picks one from what you ask, and asks you if it's unclear.

### 1. Guidance: quick questions

Answers one question, grounded in your code. Writes no files and makes no edits.

> Should I add `loading="lazy"` to every image on the home page?
>
> The dashboard chat feels slow. What should I change?
>
> Will `GET /api/orders` stay fast with thousands of orders?

### 2. Full audit: the complete report

> Run a full speedmax performance audit of this repo.

The agent measures, maps your stack, runs every applicable check, and writes a prioritized report. It then **stops and asks which findings to apply**.

### 3. Fix: apply what you approved

> Apply F-001, F-003, and all S-effort findings.

The agent works on a new branch with one commit per finding. It runs your build and tests after each fix, then re-measures and reports before/after numbers. Risky changes still need individual confirmation even if you say "all": database migrations, infrastructure, removing third-party scripts, and large refactors.

---

## How a full audit works

```text
1. Measure       Lighthouse mobile baseline, backend timings, AI time-to-first-token
2. Map           stack, routes, data layer, hosting -> every check marked
                 applicable / not applicable / blocked, with a reason
3. Check         run each applicable check from its companion file
4. Report        findings ranked by impact, then effort  -> findings.json + REPORT.md
5. Approve       you choose which findings to apply        <- stops here by default
6. Fix           branch, one commit per finding, build + tests after each
7. Re-measure    same procedure as step 1; keep fixes that helped, revert the rest
```

### Impact levels

Impact is judged against Google's Core Web Vitals thresholds (mobile, 75th percentile) and backend equivalents:

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP | ≤ 2.5 s | ≤ 4.0 s | > 4.0 s |
| INP (lab: TBT) | ≤ 200 ms | ≤ 500 ms | > 500 ms |
| CLS | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| TTFB | ≤ 0.8 s | ≤ 1.8 s | > 1.8 s |
| API p95 | ≤ 300 ms | ≤ 1 s | > 1 s |
| AI time to first token | ≤ 1 s | ≤ 3 s | > 3 s |

- **high**: moves a main route across a threshold band, or does work that grows with your data (N+1, unpaginated lists, missing indexes).
- **medium**: improvement within a band, or high impact on a secondary route.
- **low**: a marginal saving.

Effort is **S** (under an hour), **M** (up to a day), or **L** (architecture, infrastructure, or data migration).

---

## What you get

A full audit writes these files to `~/speedmax-audits/<repo>/run-<N>/`, outside your repository:

| File | Contents |
|---|---|
| `run-metadata.json` | What was audited: commit, routes, device profile, status |
| `baseline.json` | Raw and median metrics per route |
| `ledger.json` | Every check marked applicable, not applicable, or blocked, with a reason |
| `findings.json` | Machine-readable findings (see [`findings-schema.json`](findings-schema.json)) |
| `REPORT.md` | The human-readable report: summary, baseline, ranked findings, gaps |
| `after.json` | Post-fix metrics (fix mode only) |

Each finding gets one of these verdicts:

- **`confirmed`**: proven by a measurement or a concrete mechanism in your code. Only confirmed findings get an impact level.
- **`needs_measurement`**: the cause is visible in your code, but the deciding fact isn't (for example your hosting region or real traffic). The finding says exactly what to check.

Check that a run's output is well-formed:

```bash
node validate-findings.cjs ~/speedmax-audits/<repo>/run-1/findings.json ~/speedmax-audits/<repo>/run-1/ledger.json
```

---

## Safety rules

The skill tells the agent to follow these in every mode:

- Never load-test or benchmark production or shared environments.
- Ask before sending a URL to an outside service such as PageSpeed Insights.
- Ask before installing any package or tool.
- Never run migrations or create indexes on shared databases; deliver them as migration files.
- Never put secrets or customer data in reports.
- Treat a change that hurts content, accessibility, SEO, correctness, or security as a regression, not a fix.

---

## Evaluation

`eval/` tests the skill end to end with [MLflow](https://mlflow.org/blog/evaluating-improving-agent-skills/). Each case works like this:

1. Copy a test app into a throwaway git repo.
2. Run the skill headless in Claude Code.
3. Trace every tool call.
4. Score the result.

The test cases:

- **Full audit of a slow app:** a Next.js + Prisma shop with 14 planted problems.
- **Full audit of a fast app:** an already-optimized static site, to catch false positives.
- **Three quick questions:** lazy-loading images, a slow AI chat, and an orders endpoint at scale.
- **One fix run:** apply an approved finding and leave a proposed one alone.

There are 18 scorers. They check:

- **Results:** did it find the planted issues, did it avoid false positives, did the fix stay in scope.
- **Behavior:** did it measure before reporting, did it avoid making up numbers, did it stop for approval, did it avoid installs and network calls.
- **Answer quality:** a Claude judge grades each quick-question answer against a rubric.

Latest results (Sonnet as the agent, one run per case):

| Case | Checks passed |
|---|---|
| Full audit, slow app: found all 14 planted issues | 9/9 |
| Full audit, fast app: no false positives | 9/9 |
| Quick questions | 4/4 per case |
| Fix run: only the approved finding was changed | 6/6 |

Each case ran once, so results can vary between runs. Real Lighthouse runs were not tested, because the test apps have no installed dependencies. See [eval/README.md](eval/README.md) to run it yourself.

---

## Repository layout

```text
SKILL.md                     Entry point: modes, safety, principles, workflow, impact levels
MEASUREMENT.md               Measuring the baseline (MEAS-01)
RECONNAISSANCE.md            Mapping the stack and marking every check
FRONTEND-ASSETS.md           IMG-01, IMG-02, CDN-01, FONT-01, 3P-01
JAVASCRIPT-AND-BUNDLES.md    DEP-01, JS-01, UX-03
DATA-AND-BACKEND.md          DB-01, DB-02, DB-03, CACHE-01, JOB-01
PERCEIVED-PERFORMANCE.md     UX-01, UX-02
INFRASTRUCTURE.md            INFRA-01, INFRA-02
FIXING-AND-VERIFICATION.md   Approval, applying fixes, re-measuring, regression guards
REPORTING.md                 findings.json fields and REPORT.md layout
findings-schema.json         Contract for findings.json
validate-findings.cjs        Validator (no dependencies)
validate-findings.test.cjs   Validator tests: node --test validate-findings.test.cjs
eval/                        MLflow evaluation harness and test apps
```

---

## Contributing

Issues and pull requests are welcome. Good contributions include:

- **New fix recipes** for a framework or stack the companion files don't cover yet.
- **New eval cases**, especially real-world cases where the skill gave a wrong or weak answer.
- **Better detection** that cuts false positives.

Before opening a pull request:

```bash
node --test validate-findings.test.cjs
```

If you change the skill's instructions, re-run the relevant eval group:

```bash
cd eval && uv run python run_eval.py --group guidance
```

---

## License

[MIT](LICENSE)
