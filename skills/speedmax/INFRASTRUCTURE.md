# Infrastructure

#### When to use this file

Use this file when hosting location, runtime model, or startup time affect latency. These checks often depend on dashboard settings outside the repository, so many results are `needs_measurement` or `blocked` with a clear question for the owner. Checks: **INFRA-01, INFRA-02**.

## Core discipline (include in every agent prompt for this domain)

```
- Read deployment config in the repository (vercel.json, netlify.toml, wrangler.toml, fly.toml, render.yaml, app.yaml, serverless.yml, Dockerfile, Terraform, Kubernetes manifests). Do not log in to or query hosting dashboards or cloud APIs.
- Where users are, where compute runs, and where the database runs are three separate facts. Name each one and its source, or mark it unknown.
- Cold-start claims need evidence: a measured first-request time after idle on a non-production deployment, platform logs the user provides, or a source mechanism (scale-to-zero config plus heavy startup work).
- Infrastructure changes cost money and can affect availability. Every fix states its cost impact and is effort M or L unless it is a one-line config change.
- Return structured candidates. Do not edit source.
```

## INFRA-01 — Put your server close to your users

**Why it matters**
Every round trip pays the distance. A user in Nairobi calling a server in us-east-1 pays about 200–250 ms per round trip; a page that needs several sequential round trips (TLS, HTML, API, data) multiplies it. Worse, a server far from its own database pays that latency on every query: 50 queries × 70 ms is 3.5 s.

**Detect**
- Compute region: `vercel.json` `regions`, Next.js `export const preferredRegion`, `fly.toml` `primary_region`, `render.yaml` `region`, `app.yaml`/Cloud Run region in deploy scripts, `serverless.yml` `provider.region`, Terraform `region`, Cloudflare Workers (global by default; check Smart Placement).
- Database region: connection strings or env examples (`.env.example`) showing a host such as `aws-us-east-1`, `eu-west-2`, or a provider region; Prisma/Drizzle/Neon/Supabase/PlanetScale/Turso config.
- Users' location: from the owner, analytics, or field data. Code cannot show this. Mark it `needs_measurement` if unknown.
- Edge or global functions that call a single-region database (each query crosses the world).
- High TTFB in field data (PSI) relative to local TTFB.

**Evidence required**
The three locations (users, compute, database) with sources, and either measured TTFB from the users' region or the round-trip count of a main route multiplied by estimated distance latency.

**Fix**
- Put compute in the same region as the database first; this is usually the bigger win.
- Choose the region nearest most users for both.
- For global audiences: serve static and cacheable content from the CDN edge (CDN-01, CACHE-01); add read replicas near users (Neon, PlanetScale, Turso, Supabase, Aurora Global) and route reads to them; use Smart Placement or region pinning so functions run near their data.
- Reduce sequential round trips: batch API calls, server-render the first view, avoid request chains.

**Verify**
TTFB from a test location in the users' region (WebPageTest or PSI, with consent) drops; per-query latency in server logs drops after co-locating compute and database.

**Pitfalls**
- Moving a database is a migration with downtime risk and possibly data-residency implications; this is effort `L` and needs the owner's plan.
- Running edge functions far from a single-region database makes things slower, not faster.

## INFRA-02 — Kill cold starts on your main routes

**Why it matters**
Serverless functions and scale-to-zero containers start from nothing after idle. Cold starts of 1–5 s (more with large bundles, heavy imports, or database connection setup) hit the first visitor after a quiet period, which on low-traffic products is most visitors.

**Detect**
- Scale-to-zero configuration: Cloud Run `min-instances` 0 (the default), Fly `auto_stop_machines` + `min_machines_running = 0`, Render free tier, AWS Lambda without provisioned concurrency, Azure Functions consumption plan, Railway sleep, Heroku eco dynos.
- Heavy startup work in the request module: large SDK imports at module top level, ORM client generation, reading large files, synchronous initialization, many dependencies (DEP-01), and large server bundles.
- New database connection per invocation without pooling (Prisma/`pg` on serverless without a pooler, PgBouncer, Prisma Accelerate, Neon/Supabase pooled URLs, or RDS Proxy).
- Evidence from the baseline: the first request after `start` or after idle is much slower than the next ones.

**Evidence required**
The platform and its scale settings (from config, or `blocked` if only in a dashboard), measured cold vs warm first-byte time on a non-production deployment or logs the owner supplies, and the startup work in source.

**Fix**
- Keep main routes warm: Cloud Run `--min-instances=1`, Fly `min_machines_running = 1`, Lambda provisioned concurrency or SnapStart (Java/Python/.NET), Azure Premium plan always-ready instances, a paid tier on hosts that sleep. State the monthly cost.
- Make starts cheaper: smaller server bundles (tree-shake, remove unused dependencies), lazy-import heavy SDKs inside the handler that needs them, avoid top-level work.
- Use lighter runtimes where compatible: Edge/Workers runtimes (millisecond starts, but check Node API and database driver compatibility), or a long-running server for the main routes.
- Pool database connections: transaction-mode poolers (PgBouncer, Supabase/Neon pooled URLs), Prisma Accelerate, RDS Proxy, or HTTP-based drivers (Neon serverless, PlanetScale, Turso) on edge runtimes.
- Pre-render or cache main routes (CACHE-01) so most visitors never hit a cold function.

**Verify**
First request after idle (wait past the platform's idle timeout on a preview deployment) drops to near warm latency; p95 TTFB in logs or field data improves.

**Pitfalls**
- Scheduled "warmer" pings keep only one instance warm and break under concurrency; prefer platform minimum instances.
- Minimum instances cost money continuously; get the owner's approval with the number.
- Edge runtimes may not support the ORM or Node APIs in use; verify before proposing.
