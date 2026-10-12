# Reconnaissance

#### When to use this file

Use this file in Phase 2 of a full audit, after the baseline exists. It maps the target and produces `ledger.json`: a decision for every check ID, so coverage is explicit and nothing is silently skipped.

## Core discipline (include in every agent prompt for this domain)

```
- Read source and configuration only. Do not run the app, install anything, or contact external services during reconnaissance.
- Return facts with repository-relative file:line references. Mark guesses as guesses.
- Every check ID gets exactly one status: applicable, not_applicable, or blocked, with a one-line reason.
- "Not applicable" needs evidence of absence (for example: no ORM, no database driver in dependencies, no <img> or image component anywhere).
- Hosting, region, CDN, and instance settings are often outside the repository. If they decide a check, mark it blocked and name the missing fact.
```

## What to map

Run these in parallel as sub-agents on large targets; on small ones the parent does them directly.

**1. Stack and build**
- Languages, frameworks and versions (`package.json`, `Gemfile`, `requirements.txt`/`pyproject.toml`, `composer.json`, `go.mod`, `Cargo.toml`).
- Rendering model: static, server-rendered, SPA, hybrid, islands, or API only.
- Bundler (webpack, Vite, Turbopack, esbuild, Rollup, Parcel, Sprockets/Propshaft, Laravel Mix/Vite) and its config file.
- Package manager and lockfile.

**2. Routes and entry points**
- Page routes (file-based routing directories, router config, `urls.py`, `routes.rb`, `routes/web.php`).
- API routes and handlers.
- Which routes are the main ones: the landing page, the authenticated home, and any route linked from the primary navigation. These decide impact.

**3. Assets**
- Image locations (`public/`, `static/`, `assets/`, CMS or remote URLs) and how images render (`<img>`, `next/image`, `@nuxt/image`, `astro:assets`, `image_tag`, CSS backgrounds).
- Fonts: `@font-face`, Google Fonts links, `next/font`, `@fontsource/*`, Typekit.
- How static files are served: framework server, object storage, host CDN (Vercel, Netlify, Cloudflare Pages, Fly, Render, Amplify), or a configured CDN.

**4. Data layer**
- Database and ORM or query builder (Prisma, Drizzle, TypeORM, Sequelize, Knex, Mongoose, ActiveRecord, Django ORM, Eloquent, SQLAlchemy, GORM, raw SQL).
- Schema or migration files: where indexes are declared.
- Caches (Redis, Memcached, in-memory, `unstable_cache`, `Rails.cache`, Django cache framework) and HTTP caching headers.
- Queue or job systems (BullMQ, Sidekiq, Celery, RQ, Laravel queues, Inngest, Trigger.dev, Cloud Tasks, SQS, Vercel/Cloudflare queues) or the lack of one.

**5. AI features**
- LLM SDK calls (`anthropic`, `@anthropic-ai/sdk`, `openai`, `ai` (Vercel AI SDK), `langchain`, `google-genai`, `ollama`, raw `fetch` to model APIs).
- Whether responses are streamed end to end: SDK stream flag → server response → client rendering.

**6. Hosting and runtime**
- Deployment config (`vercel.json`, `netlify.toml`, `wrangler.toml`, `fly.toml`, `render.yaml`, `app.yaml`, `serverless.yml`, `Dockerfile`, Terraform, Kubernetes manifests).
- Region settings for compute and database, serverless vs long-running, and minimum instances or provisioned concurrency.

**7. Third parties**
- Every external `<script>` tag, tag manager, analytics, chat widget, A/B tool, heatmap, social embed, and video embed, with where it loads.

## Ledger rules

| Check | Typical `not_applicable` reason |
|---|---|
| MEAS-01 | Never; if it cannot run, mark it `blocked` with the reason |
| IMG-01, IMG-02 | No raster images rendered by the product |
| CDN-01 | API-only service with no static files |
| FONT-01 | Only system font stack, no web fonts |
| 3P-01 | No third-party scripts |
| DEP-01 | No package manifest |
| JS-01 | No client-side JavaScript bundle (pure server-rendered HTML with no bundler) |
| UX-03 | No search, filter-as-you-type, or autocomplete input |
| DB-01, DB-02, DB-03 | No database |
| CACHE-01 | No API or server-side data fetching |
| JOB-01 | No request path does slow work (email, file processing, AI, exports, webhooks out) |
| UX-01 | No LLM or other token-streaming feature |
| UX-02 | No asynchronous data loading in the UI |
| INFRA-01 | Static site fully served from a CDN with no origin server |
| INFRA-02 | Long-running server with no scale-to-zero |

`blocked` is for checks that apply but cannot be decided from source, for example INFRA-01 when the hosting region is set in a dashboard. Name the missing fact so the report can ask the owner.

## `ledger.json` shape

```json
{
  "target": "/abs/path/to/repo",
  "stack": { "framework": "next@15", "rendering": "hybrid", "orm": "prisma", "host": "vercel", "queue": null, "ai_sdk": "@anthropic-ai/sdk" },
  "main_routes": ["/", "/dashboard", "/products", "/products/[id]"],
  "checks": {
    "MEAS-01": { "status": "applicable", "reason": "production build runs locally" },
    "IMG-01": { "status": "applicable", "reason": "34 PNG/JPG files in public/, rendered via <img> in app/page.tsx:12" },
    "UX-01": { "status": "applicable", "reason": "messages.create without stream in app/api/chat/route.ts:18" },
    "INFRA-01": { "status": "blocked", "reason": "function region not set in vercel.json; database host region unknown" },
    "JOB-01": { "status": "not_applicable", "reason": "no request performs email, file, AI, or export work" }
  }
}
```

All 18 check IDs must appear. The validator fails a ledger that is missing one.
