# Measurement

#### When to use this file

Use this file at the start of every full audit (Phase 1), again after fixes (Phase 7), and whenever a guidance-mode answer depends on "how slow is it actually?". It covers check **MEAS-01** and defines the format of `baseline.json` and `after.json`.

## Core discipline (include in every agent prompt for this domain)

```
- Measure a production build, never a dev server. Dev builds skip minification, splitting, and image optimization.
- Use the mobile profile (Lighthouse default: emulated Moto G Power, 4x CPU slowdown, slow 4G). Desktop scores hide most problems.
- Run 3–5 times per route and report the median. Record every run's raw numbers.
- Keep conditions identical between baseline and after: same routes, build command, profile, machine, and run count.
- Never benchmark or load-test production or shared environments. External services such as PageSpeed Insights need the user's consent and a public URL.
- Do not install or download tools (including `npx --yes lighthouse`) without the user's consent. If they decline, mark metric-dependent checks `needs_measurement`.
- Record what you could not measure and why. Do not invent numbers.
```

## MEAS-01 — Run Lighthouse and PageSpeed on mobile

**Why it matters**
Every other check is ranked by how much it moves these numbers. Without a baseline, "faster" is an opinion.

**Detect (what to measure)**

1. Find the production build and serve commands from `package.json`, `Makefile`, `Procfile`, `Dockerfile`, or framework docs:
   - Next.js: `next build && next start`
   - Vite / SvelteKit / Astro: `build` then `preview`
   - Nuxt: `nuxi build && node .output/server/index.mjs`
   - Rails: `RAILS_ENV=production bin/rails assets:precompile && bin/rails s -e production`
   - Django: `DEBUG=False`, `collectstatic`, then `gunicorn`
   - Laravel: `php artisan optimize` then `php artisan serve` (or the project's container)
   - Static sites: serve the build directory with any static server.
2. Pick routes: the home or landing page, the most-used authenticated page, one list or search page, and one detail page. If authentication blocks Lighthouse, use a seeded local test account or measure public routes only and record the gap.
3. Run Lighthouse (mobile is the CLI default), only after the user agrees, since `npx --yes` downloads it:

   ```bash
   npx --yes lighthouse http://localhost:3000/ \
     --only-categories=performance \
     --output=json --output-path=./lh-home-1.json \
     --chrome-flags="--headless=new" --quiet
   ```

   Repeat 3–5 times per route. Extract from each report:
   - `audits["largest-contentful-paint"].numericValue` (ms)
   - `audits["total-blocking-time"].numericValue` (ms, the lab proxy for INP)
   - `audits["cumulative-layout-shift"].numericValue`
   - `audits["first-contentful-paint"].numericValue` (ms)
   - `audits["server-response-time"].numericValue` (ms, TTFB)
   - `audits["total-byte-weight"].numericValue` (bytes)
   - `audits["largest-contentful-paint-element"]` (which element is the LCP; IMG-02 needs it)
   - `categories.performance.score`
   - The opportunities with the largest `details.overallSavingsMs`; they seed Phase 3.
4. PageSpeed Insights (only after the user agrees to send the URL to Google, and only for a public URL). It adds field data (CrUX) from real Chrome users when the site has enough traffic:

   ```bash
   curl -s "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=<public-url>&strategy=mobile&category=performance"
   ```

   Field data (`loadingExperience.metrics`) outranks lab data when the two disagree, because it is what real users get. Report both.
5. Backend timings where there is an API or server rendering:
   - Time the main endpoints with a few sequential requests (`curl -w "%{time_starttransfer}\n" -o /dev/null -s <url>`), never a load test.
   - Enable query logging locally (Prisma `log: ['query']`, Django `django.db.backends` logger or `django-debug-toolbar`, Rails log, Laravel `DB::listen`, SQLAlchemy `echo=True`) and record queries per request for the main routes. DB-02 needs this.
   - For AI features, record time to first token and time to full response for one representative prompt using the project's own test setup or mock. UX-01 needs this.

**Evidence required**
`baseline.json` with per-route, per-run raw numbers and medians, the exact commands, the build mode, and the Lighthouse version.

**Fix**
Not applicable; this check produces the baseline. Optionally recommend adding Lighthouse CI as a regression guard (see FIXING-AND-VERIFICATION.md).

**Verify**
Phase 7 repeats this exact procedure and writes `after.json` in the same shape.

**Pitfalls**
- Measuring `localhost` hides network latency and CDN effects. TTFB and INFRA-* checks need a deployed preview or field data. Mark them `needs_measurement` rather than trusting localhost TTFB.
- Browser extensions, other open tabs, and a busy machine add noise. Use headless Chrome and keep the machine idle.
- Lighthouse scores move ±5 between runs. Compare metrics, not just the score.
- A cold first run after `build` includes server warm-up. Discard it or report it separately as a cold-start observation for INFRA-02.

## `baseline.json` shape

```json
{
  "tool": "lighthouse",
  "tool_version": "12.x",
  "profile": "mobile",
  "build_mode": "production",
  "command": "npx lighthouse http://localhost:3000/ --only-categories=performance ...",
  "routes": {
    "/": {
      "runs": [
        { "score": 0.54, "lcp_ms": 4810, "tbt_ms": 620, "cls": 0.18, "fcp_ms": 2100, "ttfb_ms": 140, "bytes": 3480000 }
      ],
      "median": { "score": 0.54, "lcp_ms": 4810, "tbt_ms": 620, "cls": 0.18, "fcp_ms": 2100, "ttfb_ms": 140, "bytes": 3480000 },
      "lcp_element": "img.hero",
      "top_opportunities": ["modern-image-formats", "unused-javascript", "render-blocking-resources"]
    }
  },
  "backend": {
    "GET /api/products": { "ttfb_ms_median": 920, "queries_per_request": 51 }
  },
  "ai": {
    "POST /api/chat": { "time_to_first_token_ms": null, "time_to_full_response_ms": 8400, "streaming": false }
  },
  "field_data": null,
  "not_measured": [
    { "what": "TTFB from users' region", "reason": "only localhost available" }
  ]
}
```
