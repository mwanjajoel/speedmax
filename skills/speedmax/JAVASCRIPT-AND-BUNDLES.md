# JavaScript and Bundles

#### When to use this file

Use this file when the product ships first-party JavaScript to the browser. Bundle size and main-thread work decide TBT/INP and delay hydration and LCP on mobile CPUs. Checks: **DEP-01, JS-01, UX-03**.

## Core discipline (include in every agent prompt for this domain)

```
- Measure bundles from a production build: the framework's build output, a bundle analyzer, or Lighthouse unused-javascript and bootup-time.
- A finding names the route, the chunk or package, its size (gzipped/brotli) and/or main-thread time, and the import that pulls it in.
- A package is unused only after checking static imports, dynamic imports, config files, scripts in package.json, CLI usage, plugins, peer dependencies, and type-only usage.
- Splitting is a fix only if the critical path for the main route gets smaller without adding a request waterfall.
- Do not install analyzers or tools without the user's approval.
- Return structured candidates. Do not edit source.
```

## DEP-01 — Remove packages your AI added but never used

**Why it matters**
AI-assisted code often adds dependencies that end up unused or duplicated (two date libraries, two HTTP clients, a full UI kit for one component). Unused runtime dependencies can still enter the bundle through side-effect imports, and every dependency costs install time, cold-start time on serverless, and supply-chain risk.

**Detect**
- Static detectors (with approval): `npx --yes knip` (best for JS/TS: finds unused files, exports, and dependencies), or `npx --yes depcheck`.
- Python: `deptry .`; Ruby: compare `Gemfile` against `require`s and Rails autoloading; PHP: `composer-unused`; Go: `go mod tidy -diff` (Go 1.23+).
- Manual check for each reported package before trusting a tool:
  - `grep -rnE "from ['\"]<pkg>|require\(['\"]<pkg>|import\(['\"]<pkg>" --exclude-dir=node_modules`
  - config files (`*.config.*`, `.babelrc`, `postcss.config`, `tailwind.config`, `eslint` configs), `package.json` scripts, CI files, Dockerfiles
  - framework plugins referenced by string name, and peer dependencies of other packages.
- Duplicate-purpose packages: `moment` + `dayjs`/`date-fns`, `axios` + native `fetch`, `lodash` + `lodash-es` + `underscore`, several icon sets, several CSS-in-JS libraries.
- Heavy packages with lighter options: `moment` → `date-fns`/`dayjs`/`Intl`; full `lodash` → per-method imports or native code; `uuid` → `crypto.randomUUID()`.
- Packages in `dependencies` that only tooling uses (belong in `devDependencies`).

**Evidence required**
Per package: why it is unused or duplicated (search results), whether it reaches the client bundle (analyzer or build output), and its installed or bundled size.

**Fix**
Remove with the project's package manager (`npm uninstall`, `pnpm remove`, `yarn remove`, `bun remove`, `poetry remove`, `bundle remove`, `composer remove`) so the lockfile updates. Replace duplicates with the one the codebase uses most. Move tooling-only packages to `devDependencies`.

**Verify**
Build, typecheck, lint, and tests pass. Bundle size drops when the package was in the client bundle. Lockfile diff only removes what was intended.

**Pitfalls**
- Tools give false positives for packages used through config, string-based plugin loading, CLI binaries, CSS imports, and type-only imports. Verify each one by hand.
- Do not remove polyfills without checking the supported browser list.
- Keep each removal small enough to revert on its own.

## JS-01 — Split your JavaScript so pages load only what they need

**Why it matters**
A single large bundle makes every page download, parse, and execute code for every other page. On a mid-range phone, parsing and executing 1 MB of JavaScript can take several seconds, which shows up as TBT/INP and late hydration.

**Detect**
- Build output per route: Next.js prints first-load JS per route; Vite/Rollup with `rollup-plugin-visualizer`; webpack with `webpack-bundle-analyzer`; `source-map-explorer` for any bundle with source maps.
- Lighthouse audits: `unused-javascript`, `bootup-time`, `mainthread-work-breakdown`, `total-byte-weight`.
- Heavy libraries imported at the top level but used only on interaction or on one route: charts, rich-text editors, maps, PDF, syntax highlighting, date pickers, 3D, markdown renderers, and AI SDK client code.
- Next.js App Router: `"use client"` high in the tree (layout or page) that drags whole subtrees into the client bundle.
- Barrel imports (`import { x } from '@/components'` or from icon or UI libraries) that defeat tree-shaking.
- SPAs with routes registered without lazy loading.

**Evidence required**
The route, its JavaScript size before and after compression, and the largest modules in its critical chunks with the import that pulls each one in.

**Fix**
- **Route-level splitting**: React Router `lazy()` routes or `React.lazy` + `Suspense`; Vue Router `component: () => import('./Page.vue')`; Angular `loadComponent`/`loadChildren`. Next.js, Nuxt, SvelteKit, Remix, and Astro split by route automatically, so look for what defeats it.
- **Component-level**: load heavy, below-the-fold, or interaction-only components on demand: `next/dynamic(() => import('./Chart'), { ssr: false, loading: () => <ChartSkeleton/> })`, `defineAsyncComponent`, `{#await import(...)}`, Astro islands with `client:visible`/`client:idle`.
- **Library-level**: import specific modules (`lodash/debounce`, `date-fns/format`); set Next.js `experimental.optimizePackageImports` for barrel-heavy libraries; avoid barrel files in your own code on hot paths.
- **Server-first**: in React Server Components frameworks, move `"use client"` down to the smallest interactive leaf.
- Load polyfills only for browsers that need them.

**Verify**
First-load JavaScript for the main route drops; TBT and LCP improve or stay level; no new request waterfall appears in the Lighthouse network chain; on-demand components show a loading state (UX-02).

**Pitfalls**
- Do not lazy-load what renders above the fold; it delays LCP.
- Over-splitting into many tiny chunks adds request overhead; target large, rarely used code.
- `ssr: false` removes server rendering for that component, which can hurt SEO and LCP if it holds main content.

## UX-03 — Debounce search inputs

**Why it matters**
Firing a request (or a heavy filter) on every keystroke wastes server capacity, causes out-of-order results, and makes typing feel slow (INP). Debouncing waits until the user pauses.

**Detect**
- Inputs with `onChange`/`@input`/`on:input`/`oninput`/`keyup` handlers that call `fetch`, an API client, a router/search-param update, or a filter over a large array: `grep -rnE "on(Change|Input|KeyUp)|@input|on:input|addEventListener\(['\"](input|keyup)" --include='*.{tsx,jsx,vue,svelte,ts,js}'`, then inspect the handler.
- Autocomplete or type-ahead components without debounce or throttle.
- Missing cancellation of stale requests (`AbortController`, request IDs, React Query/SWR keys).

**Evidence required**
The input, the handler, and what each keystroke triggers (a request or computation, with its cost when measurable), for example: "typing 'running shoes' fires 13 requests to /api/search".

**Fix**
- Debounce 250–300 ms for network requests; 100–150 ms for local filtering of large lists.
- React: a `useDebouncedValue` hook or `use-debounce`; `useDeferredValue` for expensive local rendering. Vue: `watchDebounced` from VueUse. Svelte: a small debounce store. Plain JS: a 5-line `debounce` helper (no dependency needed).
- Cancel the previous request with `AbortController`, or let a data library (TanStack Query, SWR) key requests by the debounced term so stale results are ignored.
- Skip requests for empty or very short terms (fewer than 2 characters) where that matches the product.
- Show a small inline loading indicator while searching (UX-02).

**Verify**
Typing a 10-character term triggers one or two requests instead of ten; no out-of-order results; INP for typing stays under 200 ms (measure with the Performance panel or a Web Vitals log).

**Pitfalls**
- Do not debounce the visible input value itself; the field must update immediately. Debounce the side effect only.
- Do not debounce actions that should be instant (submit on Enter).
- Very long debounce (> 500 ms) makes search feel broken.
