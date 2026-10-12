# speedmax

A reusable AI agent skill that audits any web app, API, or AI product for performance, then applies the fixes you approve and proves each one with a before/after measurement.

It follows the structure of Cloudflare's [security-audit-skill](https://github.com/cloudflare/security-audit-skill). It has an entry `SKILL.md` with operating modes and safety rules, companion files per domain, a JSON findings contract, and a zero-dependency validator.

## What it checks

| ID | Check |
|---|---|
| MEAS-01 | Measure first: Lighthouse and PageSpeed on mobile |
| IMG-01 | Compress images to WebP or AVIF |
| IMG-02 | Lazy-load images below the fold (never the LCP image) |
| CDN-01 | Serve static files from a CDN with long-lived caching |
| FONT-01 | Preload the main font, and use only 1–2 fonts |
| 3P-01 | Remove third-party scripts you don't need |
| DEP-01 | Remove packages that were added but never used |
| JS-01 | Split JavaScript so pages load only what they need |
| UX-03 | Debounce search inputs |
| DB-01 | Add database indexes on columns you filter by |
| DB-02 | Fix N+1 queries |
| DB-03 | Paginate lists instead of loading everything |
| CACHE-01 | Cache API responses that rarely change |
| JOB-01 | Move heavy work to background jobs |
| UX-01 | Stream AI responses instead of waiting for the full answer |
| UX-02 | Show skeletons and loading states, not blank screens |
| INFRA-01 | Put your server close to your users |
| INFRA-02 | Kill cold starts on your main routes |

## How it works

1. **Measure** a production build on mobile (median of 3–5 Lighthouse runs) and record backend and AI timings.
2. **Map** the stack and mark every check applicable, not applicable, or blocked.
3. **Check** each applicable item and record evidence.
4. **Report** findings, prioritized by user-visible impact and then effort.
5. **Stop for approval.** No source is changed until you approve findings by ID.
6. **Fix** on a branch, one commit per finding.
7. **Re-measure** and keep only fixes that moved their metric.

## Install

Claude Code (user-wide):

```bash
git clone <this-repo> ~/.claude/skills/speedmax
```

Or per project, at `.claude/skills/speedmax/`. Other agents can load `SKILL.md` as instructions; the companion files are linked from it.

## Use

- Guidance: "Why is my landing page LCP so high?" or "Is this an N+1?"
- Full audit: "Run a full speedmax performance audit of this repo."
- Fix: "Apply F-001, F-003 and all S-effort findings."

Validate artifacts:

```bash
node validate-findings.cjs ~/speedmax-audits/<repo>/run-1/findings.json ~/speedmax-audits/<repo>/run-1/ledger.json
node --test validate-findings.test.cjs
```

## Evaluation

`eval/` runs the skill through Claude Code against fixture apps with planted issues and scores the results with MLflow. See [eval/README.md](eval/README.md).

## License

MIT
