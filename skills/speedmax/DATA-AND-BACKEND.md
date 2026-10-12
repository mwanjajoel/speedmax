# Data and Backend

#### When to use this file

Use this file when the product has a server, API, or database. These checks decide TTFB, API latency, and how cost grows with data size. Checks: **DB-01, DB-02, DB-03, CACHE-01, JOB-01**.

## Core discipline (include in every agent prompt for this domain)

```
- A finding names the endpoint or page, the query or code path (file:line), and its cost: query count per request, rows scanned, latency, or how it grows with data size.
- Prove database claims with EXPLAIN / EXPLAIN ANALYZE or query logs on a local or disposable database with representative data. Never run them against shared, staging, or production databases.
- Before any database command, check where the connection goes: the host must be `localhost`, `127.0.0.1`, a Unix socket, a SQLite file, or a container you started for this audit. A remote host in `DATABASE_URL` or `.env` means stop and ask, even if it is labelled dev. `EXPLAIN ANALYZE` executes the query, including any writes in it.
- Index and schema changes are delivered as migration files. Never apply them to a non-local database.
- A cache needs a stated owner of freshness: TTL, invalidation trigger, and what users see when data is stale. No invalidation plan, no finding.
- A background job is a fix only when the user does not need the result in the same response.
- Return structured candidates. Do not edit source.
```

## DB-01 — Add database indexes on columns you filter by

**Why it matters**
Without an index, filtering, joining, or sorting scans the whole table. The query gets slower as the table grows, and it stays fast in development where tables are small.

**Detect**
- Collect the columns used in `WHERE`, `JOIN ... ON`, `ORDER BY`, and `GROUP BY` from hot queries:
  - Prisma `where:`/`orderBy:`, Drizzle `where(eq(...))`, TypeORM `find({ where })`, Sequelize `findAll({ where })`, Mongoose `find({...})`/`sort`, ActiveRecord `where`/`order`/`find_by`, Django `filter`/`exclude`/`order_by`/`get`, Eloquent `where`/`orderBy`, SQLAlchemy `filter`/`filter_by`, raw SQL.
- Compare against declared indexes: Prisma `@@index`/`@unique`/`@id`; Drizzle `index()`; Rails `add_index` / `db/schema.rb`; Django `db_index=True`, `Meta.indexes`; Laravel `$table->index()`; SQL `CREATE INDEX`; Mongoose `schema.index()`.
- Common misses: foreign keys (Postgres does not index them automatically), `user_id`/`tenant_id`/`org_id` filters, `status` + `created_at` combinations, `slug`/`email` lookups, soft-delete `deleted_at IS NULL` filters, case-insensitive lookups (`lower(email)`).
- Confirm with `EXPLAIN (ANALYZE, BUFFERS)` (Postgres), `EXPLAIN ANALYZE` (MySQL 8+), `EXPLAIN QUERY PLAN` (SQLite), or `.explain("executionStats")` (MongoDB) on a seeded local database. Look for `Seq Scan`/`type: ALL`/`COLLSCAN` on large tables and a high rows-examined to rows-returned ratio.

**Evidence required**
The query, its call site, the plan showing a full scan (or the missing index plus the table's expected size when no local data exists), and how often the route runs it.

**Fix**
- Add the index in a migration in the project's tool. Use composite indexes in the order equality columns first, then range or sort columns (for example `(tenant_id, status, created_at)`).
- Use partial indexes for common filtered subsets (`WHERE deleted_at IS NULL`) and expression indexes for `lower(email)`.
- On Postgres production tables, use `CREATE INDEX CONCURRENTLY` (Rails `algorithm: :concurrently` with `disable_ddl_transaction!`; Django `AddIndexConcurrently`; raw migration in Prisma/Drizzle) to avoid locking writes. Note this in the finding.

**Verify**
`EXPLAIN` shows an index scan; local query time drops; endpoint latency improves on seeded data.

**Pitfalls**
- Every index slows writes and uses storage. Do not index columns no query uses, low-cardinality columns alone (a boolean), or tiny tables.
- Check for an existing composite index whose leading column already covers the query.
- Index creation on large tables can lock writes; flag migrations that need a maintenance window.

## DB-02 — Fix N+1 queries

**Why it matters**
Loading a list and then querying once per item turns 1 query into N+1. It looks fine with 10 rows and collapses with 1,000. It is common in AI-generated code that loops over results and awaits a query inside the loop.

**Detect**
- Queries inside loops: `for`/`forEach`/`map` (including `Promise.all(items.map(async ...))`) that call the ORM, and template loops that touch a relation (`{% for o in orders %}{{ o.customer.name }}`, `@foreach($posts as $post) {{ $post->author->name }}`, `<% @posts.each do |p| %><%= p.author.name %>`).
- GraphQL resolvers that fetch a relation per parent without a DataLoader.
- Query logs: count queries per request for main routes (from the MEAS-01 baseline). Repeated identical-shape queries with different IDs are the signature.
- Tools: Rails `bullet` or `strict_loading`; Django `nplusone`, `django-debug-toolbar`, or `assertNumQueries` in tests; Laravel `Model::preventLazyLoading()`; Prisma/Drizzle query logging.

**Evidence required**
The route, queries per request (for example "51 queries for 50 orders"), the loop and the lazy relation access (file:line).

**Fix**
- Eager-load: Prisma `include`/`select` on the relation; Drizzle relational queries `with:`; TypeORM `relations`/`leftJoinAndSelect`; Sequelize `include`; ActiveRecord `includes`/`preload`/`eager_load`; Django `select_related` (FK, one-to-one) and `prefetch_related` (many); Eloquent `with()`; SQLAlchemy `selectinload`/`joinedload`; Mongoose `populate` (or `$lookup`).
- Batch: collect IDs, then one `WHERE id IN (...)` query, then map results in memory.
- GraphQL: a per-request DataLoader for every relation resolver.
- Add a guard so it does not come back: `strict_loading`, `preventLazyLoading()`, or a test asserting query count.

**Verify**
Query count per request becomes constant (independent of N); latency drops on seeded data with many rows.

**Pitfalls**
- Eager-loading large relations you do not render wastes memory; select only the columns needed.
- A JOIN that multiplies rows (several one-to-many relations at once) can be worse than separate batched queries; prefer `prefetch`/`selectinload` style for many-relations.

## DB-03 — Paginate lists instead of loading everything

**Why it matters**
Endpoints and pages that return every row get slower and heavier as data grows, increase memory, and send megabytes to phones that show 20 items.

**Detect**
- List queries without a limit: `findMany()` without `take`, `find({})` without `.limit()`, `Model.all`, `.objects.all()` rendered or serialized fully, `Model::all()`/`->get()` without `paginate`, `SELECT ... FROM` without `LIMIT`.
- API responses returning arrays with no `limit`/`cursor`/`page` parameters.
- Client code that fetches everything and filters or slices in the browser.
- Large tables rendered without virtualization.

**Evidence required**
The endpoint or page, the unbounded query, current or expected row count, and response size or render time when measurable.

**Fix**
- Server-side limit with a sensible default and maximum (for example 20 default, 100 max).
- Cursor (keyset) pagination for large or frequently-changing tables: `WHERE (created_at, id) < ($1, $2) ORDER BY created_at DESC, id DESC LIMIT 20`, with an index on the sort columns (DB-01). Prisma `cursor` + `take`; Rails `pagy` keyset or `where(...).limit`; Django `CursorPagination` (DRF); Laravel `cursorPaginate()`.
- Offset pagination (`LIMIT/OFFSET`, `paginate()`) is fine for small tables or when users need page numbers; it slows down on deep pages.
- Client: infinite scroll or "Load more" with TanStack Query `useInfiniteQuery`/SWR Infinite; virtualize long lists (`@tanstack/react-virtual`, `vue-virtual-scroller`).
- Select only needed columns in list views.

**Verify**
Response size and latency stay flat as data grows (test with seeded data at 10× current size); the page renders the first items quickly.

**Pitfalls**
- Changing an existing API's response shape breaks clients. Add pagination parameters with backward-compatible defaults or version the endpoint, and say so in the finding.
- `COUNT(*)` for total pages can be expensive on large tables; omit it or estimate.
- Exports and reports that need all rows belong in a background job (JOB-01), not an unpaginated request.

## CACHE-01 — Cache API responses that rarely change

**Why it matters**
Recomputing the same answer for every request (config, categories, pricing, public content, expensive aggregations, third-party API results) wastes server time and adds TTFB.

**Detect**
- GET endpoints and server data fetches whose data changes rarely compared with how often they are read: settings, navigation, product catalogs, feature flags, public profiles, CMS content, exchange rates, third-party lookups.
- Missing HTTP caching headers on those responses (`Cache-Control`, `ETag`, `Last-Modified`).
- Framework caching turned off or misused: Next.js `export const dynamic = 'force-dynamic'`, `cache: 'no-store'`, or `revalidate = 0` on mostly-static pages; no `Rails.cache.fetch`; no Django `cache_page`/low-level cache; no Laravel `Cache::remember`.
- Repeated identical external API calls per request.
- Client refetching the same data on every mount without a data cache (TanStack Query, SWR, Apollo).

**Evidence required**
The endpoint, how often the data changes (from code: who writes it), how expensive the read is (latency, queries, or external calls), and the current caching headers or layer.

**Fix** (pick the outermost layer that is correct)
1. **HTTP / CDN**: public data → `Cache-Control: public, s-maxage=300, stale-while-revalidate=86400`; per-user data → `private, max-age=60` or `ETag` with 304 responses. Never `public` for user-specific data.
2. **Framework**: Next.js `revalidate` / `fetch(..., { next: { revalidate, tags } })` + `revalidateTag` on writes; Nuxt `routeRules` with `swr`/`isr`; SvelteKit `setHeaders`; Astro static or hybrid rendering.
3. **Application cache**: Redis or Memcached via `Rails.cache.fetch(key, expires_in:)`, Django cache framework, Laravel `Cache::remember`, or a small TTL cache in Node; invalidate on writes.
4. **Client**: TanStack Query/SWR with `staleTime` so navigation does not refetch.

State the invalidation rule in the finding: "invalidate `categories` tag in `createCategory` and `updateCategory`; worst case 5 minutes stale".

**Verify**
Second request is served from cache (cache-status header, log, or timing); TTFB for that endpoint drops; writes still appear within the stated staleness window.

**Pitfalls**
- Caching per-user or permission-dependent data in a shared cache leaks data between users. Include the user or tenant in the key, or use `private`.
- Caching without invalidation creates bugs that look like data loss. No invalidation plan, no cache.
- Do not cache error responses for long.

## JOB-01 — Move heavy work to background jobs

**Why it matters**
Sending email, resizing images, generating PDFs or exports, calling slow third-party or AI APIs, and fanning out webhooks inside the request makes users wait and causes timeouts on serverless platforms.

**Detect**
- Request handlers that `await` email sending (`nodemailer`, `resend`, `sendgrid`, `ActionMailer#deliver_now`, Django `send_mail`, Laravel `Mail::send`), image or PDF processing (`sharp`, `puppeteer`, `ImageMagick`, `wkhtmltopdf`), CSV/Excel exports, bulk inserts, outbound webhooks, or LLM calls whose result the user does not need immediately (summaries, embeddings, classification).
- Endpoints with high p95 latency in the baseline, or close to platform timeouts (10–60 s on many serverless hosts).
- Existing queue infrastructure that the slow path does not use.

**Evidence required**
The handler, the slow operation, its measured or estimated duration, and why the response does not need to wait for it.

**Fix**
- Respond fast (`202 Accepted` or an optimistic UI), and enqueue the work: BullMQ/Graphile Worker (Node), Inngest or Trigger.dev (serverless-friendly), Sidekiq/Solid Queue/`deliver_later` (Rails), Celery/RQ/Django-Q/Dramatiq (Python), Laravel queues (`ShouldQueue`), Cloud Tasks/SQS/Cloudflare Queues, or platform `waitUntil`/`after()` for short fire-and-forget work.
- Report progress with polling, Server-Sent Events, or a webhook, and show status in the UI (UX-02).
- Make jobs idempotent and retryable.

**Verify**
The endpoint's latency drops to the enqueue time; the job completes and its result appears; failures retry and are visible.

**Pitfalls**
- `waitUntil`/`after()` is not a durable queue; use it only for work that can be lost.
- Adding a queue adds infrastructure. If none exists, this is effort `M` or `L`; say so.
- Do not move work to the background when the user needs its result in the same view (stream it instead: UX-01).
