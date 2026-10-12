# speedmax

A coding-agent skill that turns your agent into a performance engineer. It measures your app on mobile, maps the stack, runs 18 performance checks, reports findings ranked by user-visible impact, applies only the fixes you approve, and re-measures to prove each one worked.

It works on any codebase, with fix recipes for Next.js, React/Vite, Nuxt, SvelteKit, Astro, Rails, Django, Laravel, Express/Prisma, and plain HTML.

## What it does

The skill runs a structured audit in seven phases:

1. **Measure** -- record a mobile Lighthouse baseline (median of 3–5 runs), backend timings, and AI time-to-first-token in `baseline.json`.
2. **Reconnaissance** -- map the stack, routes, data layer, hosting, and third parties, and mark every check `applicable`, `not_applicable`, or `blocked` with a reason in `ledger.json`.
3. **Check** -- run each applicable check from its companion file and record evidence.
4. **Report** -- write findings ranked by impact, then effort, to `findings.json`, validate them against `findings-schema.json`, and derive `REPORT.md`.
5. **Approval gate** -- stop and ask which findings to apply. Nothing in the source changes before this.
6. **Fix** -- apply approved findings on a branch, one commit per finding, running the build and tests after each.
7. **Re-measure** -- repeat the Phase 1 measurement, record `after.json`, keep fixes that moved their metric, and revert the rest.

The agent runs `validate-findings.cjs` after Phase 4 and again after Phase 7.

The verdicts are distinct. `confirmed` has a measurement or a concrete source mechanism, plus an impact level. `needs_measurement` names the exact fact that would decide it, such as a hosting region or real traffic, and has no impact level.

The 18 checks:

| ID | Check |
|----|-------|
| `MEAS-01` | Measure first: run Lighthouse and PageSpeed on mobile |
| `IMG-01` | Compress every image to WebP or AVIF |
| `IMG-02` | Lazy-load images below the fold (never the LCP image) |
| `CDN-01` | Serve static files from a CDN |
| `FONT-01` | Preload your main font, and use only 1–2 fonts |
| `3P-01` | Remove third-party scripts you don't need |
| `DEP-01` | Remove packages that were added but never used |
| `JS-01` | Split your JavaScript so pages load only what they need |
| `UX-03` | Debounce search inputs |
| `DB-01` | Add database indexes on columns you filter by |
| `DB-02` | Fix N+1 queries |
| `DB-03` | Paginate lists instead of loading everything |
| `CACHE-01` | Cache API responses that rarely change |
| `JOB-01` | Move heavy work to background jobs |
| `UX-01` | Stream AI responses instead of waiting for the full answer |
| `UX-02` | Show skeletons and loading states, not blank screens |
| `INFRA-01` | Put your server close to your users |
| `INFRA-02` | Kill cold starts on your main routes |

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Operating modes, execution safety, core principles, impact thresholds, workflow overview, and anti-patterns |
| `MEASUREMENT.md` | Phase 1 measurement procedure (`MEAS-01`) and the `baseline.json` format |
| `RECONNAISSANCE.md` | Phase 2 stack mapping and the `ledger.json` coverage rules |
| `FRONTEND-ASSETS.md` | Images, lazy-loading, CDN, fonts, and third-party scripts (`IMG-01`, `IMG-02`, `CDN-01`, `FONT-01`, `3P-01`) |
| `JAVASCRIPT-AND-BUNDLES.md` | Unused packages, code splitting, and debounced search (`DEP-01`, `JS-01`, `UX-03`) |
| `DATA-AND-BACKEND.md` | Indexes, N+1 queries, pagination, response caching, and background jobs (`DB-01`, `DB-02`, `DB-03`, `CACHE-01`, `JOB-01`) |
| `PERCEIVED-PERFORMANCE.md` | Streaming AI responses and loading states (`UX-01`, `UX-02`) |
| `INFRASTRUCTURE.md` | Server and database region, and cold starts (`INFRA-01`, `INFRA-02`) |
| `FIXING-AND-VERIFICATION.md` | Phases 5–7: approval gate, applying fixes, re-measuring, and regression guards |
| `REPORTING.md` | `findings.json` field rules and the `REPORT.md` layout |
| `findings-schema.json` | JSON schema for `findings.json` |
| `validate-findings.cjs` | Zero-dependency validator for `findings.json` and `ledger.json` |
| `validate-findings.test.cjs` | Validator tests |

All skill files live in `skills/speedmax/`. The `eval/` directory holds the MLflow evaluation harness; it is not part of the installed skill.

## Installation

Install the skill with the [Skills CLI](https://skills.sh):

```bash
npx skills add https://github.com/mwanjajoel/speedmax \
  --skill speedmax
```

Use `--global` for a user-level installation:

```bash
npx skills add https://github.com/mwanjajoel/speedmax \
  --skill speedmax \
  --global
```

To pin a released version instead of tracking `main`, install from a tag:

```bash
npx skills add https://github.com/mwanjajoel/speedmax/tree/v0.1.0 \
  --skill speedmax
```

Run `npx skills --help` for agent-selection and non-interactive options.

## Usage

Start your coding agent in (or pointed at) the codebase you want to speed up, then ask it:

```
run a speedmax performance audit of this repo
```

```
why is the LCP on my landing page so high?
```

```
apply F-001, F-003 and all S-effort findings
```

The skill activates automatically when the request matches its trigger: making a page, endpoint, query, or AI feature faster, Lighthouse scores, Core Web Vitals, images, fonts, bundles, N+1 queries, caching, streaming, cold starts, and so on.

- **Full audit mode:** used for an explicit audit request or a "speed up this app" request. It runs Phases 1–4 and stops at the approval gate.
- **Guidance mode:** used for focused questions. It reads the relevant code and answers without writing files or editing source.
- **Fix mode:** applies only the findings you approve by ID. Database migrations, infrastructure changes, removing third-party scripts, and `L`-effort findings need individual confirmation even when you approve "all".

In full audit mode, an unspecified output directory defaults to `~/speedmax-audits/<repo-name>/run-<N>`. The workflow writes inside the target repository only when you explicitly choose a directory that version control ignores.

## Requirements

- A coding agent with a model that supports tool use. Parallel sub-agents help on large codebases but are optional.
- Node.js 18 or later for the zero-dependency validator.
- Chrome and Lighthouse (`npx lighthouse`) for real measurements. The agent asks before installing or running them. Without them, metric-dependent checks are recorded as `needs_measurement` instead of guessed.
- A local production build, preview deployment, or staging URL to measure. The skill does not load-test or benchmark production or shared environments.

## Design principles

- **Measure first.** No finding without a baseline number or a source-grounded mechanism. One Lighthouse run is noise; use the median of several.
- **Impact over checklists.** A finding names the route, the metric it moves, and by how much. Missing best practices with no measurable cost are not findings.
- **Respect what is out of source.** Hosting region, CDN defaults, and real traffic are often invisible in the repository. When the deciding fact is unseen, the verdict is `needs_measurement`.
- **You approve every change.** Audits never edit source. Fixes land on a branch, one commit per finding.
- **Prove it or revert it.** A fix that does not move its metric is reverted and recorded as `reverted`.
- **Behavior is the constraint.** A change that hurts content, accessibility, SEO, correctness, or security in exchange for a better score is a regression.

## Evaluation

`eval/` tests the skill end to end with [MLflow](https://mlflow.org/blog/evaluating-improving-agent-skills/). Each case runs headless in Claude Code against a fixture app and is traced and scored. Six cases cover:

- a full audit of a slow app with 14 planted issues
- a full audit of an already-optimized app (false positives)
- three guidance questions
- one fix run

In the latest run, every case passed all its checks. The slow-app audit found all 14 planted issues, and the fix run changed only the approved finding. Each case ran once, and real Lighthouse runs were not exercised, because the fixtures have no installed dependencies. See [eval/README.md](eval/README.md) to run it.

## License

MIT -- see [LICENSE](LICENSE).
