# Frontend Assets

#### When to use this file

Use this file when the product ships HTML to a browser: images, fonts, static files, and third-party scripts. These usually decide LCP, CLS, and transfer size on mobile. Checks: **IMG-01, IMG-02, CDN-01, FONT-01, 3P-01**.

Use alongside `JAVASCRIPT-AND-BUNDLES.md` for first-party JavaScript weight and `PERCEIVED-PERFORMANCE.md` for loading states.

## Core discipline (include in every agent prompt for this domain)

```
- Start from the baseline: the LCP element, total byte weight, and Lighthouse opportunities for each main route.
- A finding names the route, the element or file, its current cost (bytes, ms, or CLS), and the source location that emits it.
- The LCP element and everything above the fold load eagerly with high priority. Never lazy-load them.
- Framework image, font, and script components already apply many fixes. Check what they do before proposing a change.
- Visual output must not change: same image framing, legible text, no layout shift, no missing tracking the business relies on.
- Return structured candidates. Do not edit source.
```

## IMG-01 — Compress every image to WebP or AVIF

**Why it matters**
Images are usually the largest bytes on a page and often the LCP element. AVIF is typically 50% smaller than JPEG and WebP 25–35% smaller at the same visual quality. Oversized dimensions waste even more than format.

**Detect**
- Large files: `find . -path ./node_modules -prune -o \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.gif' \) -size +100k -print`
- Raw tags bypassing the framework optimizer: `grep -rnE '<img\s' --include='*.{tsx,jsx,vue,svelte,astro,html,erb,blade.php}'`
- Images served at larger intrinsic size than displayed, and missing `srcset`/`sizes`. Lighthouse audits: `modern-image-formats`, `uses-optimized-images`, `uses-responsive-images`.
- Next.js `images.unoptimized: true` or `next/image` with `unoptimized`. Remote image hosts that are not configured, which forces `unoptimized`.
- Animated GIFs (replace with `<video autoplay muted loop playsinline>` in MP4/WebM).
- CSS `background-image` heroes, which cannot use `srcset` without `image-set()`.

**Evidence required**
Per image: file, current format, bytes, displayed size vs intrinsic size, and the route. The Lighthouse savings estimate when available.

**Fix**
- **Next.js**: use `next/image` with `width`/`height` or `fill` + `sizes`; set `images.formats: ['image/avif', 'image/webp']` in `next.config`; add `remotePatterns` for remote hosts.
- **Nuxt**: `@nuxt/image` `<NuxtImg format="avif,webp" sizes="...">` or `<NuxtPicture>`.
- **Astro**: `<Image>` / `<Picture formats={['avif','webp']}>` from `astro:assets`.
- **SvelteKit / Vite**: `@sveltejs/enhanced-img` or `vite-imagetools` (`?format=avif;webp&w=480;960;1440&as=picture`).
- **Rails**: Active Storage variants with `format: :webp`, or pre-converted assets with `picture_tag`.
- **Django / Laravel / plain HTML**: convert at build time (`sharp`, `squoosh-cli`, `cwebp`, `avifenc`, Python `Pillow`) and emit:

  ```html
  <picture>
    <source type="image/avif" srcset="hero-640.avif 640w, hero-1280.avif 1280w" sizes="100vw">
    <source type="image/webp" srcset="hero-640.webp 640w, hero-1280.webp 1280w" sizes="100vw">
    <img src="hero-1280.jpg" alt="..." width="1280" height="720">
  </picture>
  ```
- **User uploads**: convert on upload in a background job (JOB-01) or use an image CDN (Cloudflare Images, imgix, Cloudinary, Vercel/Netlify image optimization).
- Always set `width` and `height` (or `aspect-ratio`) to prevent CLS.

**Verify**
Re-run Lighthouse: total byte weight and LCP drop on affected routes; `modern-image-formats` passes. Compare the images visually.

**Pitfalls**
- Keep a JPEG/PNG fallback inside `<picture>` for old clients.
- Do not recompress logos and line art as lossy AVIF; use SVG or lossless WebP.
- Very aggressive quality settings (below ~50 for AVIF) show artifacts on faces and gradients.

## IMG-02 — Lazy-load images below the fold

**Why it matters**
Images below the first screen compete for bandwidth with the LCP image. Deferring them speeds up LCP and saves data for users who never scroll.

**Detect**
- `<img>` tags without `loading="lazy"` that render in lists, galleries, footers, carousels, or below the hero.
- Framework components where lazy is the default (`next/image`, `NuxtImg`, Astro `<Image>`): check the opposite mistake, where the LCP image is lazy because `priority`/`fetchpriority`/`loading="eager"` is missing.
- The baseline's `lcp_element`. Lighthouse audits: `offscreen-images`, `lcp-lazy-loaded`, `prioritize-lcp-image`.
- `<iframe>` embeds (maps, videos) without `loading="lazy"`.

**Evidence required**
The route, the list of below-the-fold images loaded eagerly (count and bytes), and the LCP element's current loading attributes.

**Fix**
- Below the fold: `<img loading="lazy" decoding="async" ...>`; `<iframe loading="lazy">`.
- The LCP image: `loading="eager"` (or omit) plus `fetchpriority="high"`. In Next.js use `priority` (or `preload` on newer versions); in Nuxt `preload`; in Astro `loading="eager" fetchpriority="high"`.
- For a CSS background LCP image, add `<link rel="preload" as="image" href="..." fetchpriority="high">` or switch to an `<img>`.

**Verify**
Fewer bytes before LCP in the Lighthouse network waterfall; `lcp-lazy-loaded` and `offscreen-images` pass; LCP unchanged or better.

**Pitfalls**
- Never lazy-load the LCP image or the first visible row of a product grid; this is the most common speed regression.
- Lazy images need dimensions or they cause CLS when they appear.
- Avoid JavaScript lazy-load libraries where native `loading="lazy"` works.

## CDN-01 — Serve static files from a CDN

**Why it matters**
A CDN serves JS, CSS, fonts, and images from a location near the user and takes load off the origin. With content-hashed filenames, files can be cached forever.

**Detect**
- The host already provides a CDN (Vercel, Netlify, Cloudflare Pages, Firebase Hosting, Amplify, Render static sites). If so, this check is mostly about cache headers.
- Static files served by the app server: Express `express.static`, Django `whitenoise` or `django.contrib.staticfiles` in production, Rails `public_file_server`, Laravel `public/` through PHP-FPM, Flask `send_from_directory`.
- Missing or short caching headers on hashed assets: look for `Cache-Control` config, `headers()` in `next.config`, `_headers` (Netlify/Cloudflare), `vercel.json` headers, nginx `expires`.
- Unhashed filenames (`app.js`, `styles.css`) that cannot be cached long.
- Lighthouse audit: `uses-long-cache-ttl`.

**Evidence required**
Where static files are served from, the `Cache-Control` header for a hashed asset (from config, or a local `curl -I`), and whether the filenames are hashed.

**Fix**
- Hashed assets: `Cache-Control: public, max-age=31536000, immutable`.
- HTML: `Cache-Control: no-cache` (or a short `s-maxage` with `stale-while-revalidate` when content allows).
- Without a CDN: point the asset host at one (Rails `config.asset_host`, Django `STATIC_URL` to a CDN origin, Laravel `ASSET_URL`, Next.js `assetPrefix`, Vite `base`) backed by Cloudflare, CloudFront, Fastly, or Bunny. For small apps, putting the whole site behind a CDN proxy (for example Cloudflare) is the smallest change.
- Upload build output to object storage with the right headers in CI if the app server currently serves it.

**Verify**
`curl -I` on a hashed asset shows the immutable header and a CDN cache status header (`cf-cache-status`, `x-vercel-cache`, `x-cache`) on the second request. Lighthouse `uses-long-cache-ttl` passes. TTFB for static files drops on a deployed preview.

**Pitfalls**
- Never set long caching on unhashed filenames or HTML; users get stale apps.
- Do not stack a second CDN in front of a host that already has one unless there is a specific reason.
- Cookies on asset requests can disable CDN caching; serve assets from a cookieless path or domain.
- Unhashed files in `public/` cannot be cached `immutable`. Recommend fingerprinting them (import through the bundler) or a short `max-age` with `stale-while-revalidate`. What the host does by default for files without explicit headers is outside source: record it as `needs_measurement` unless you checked a real response.

## FONT-01 — Preload the main font, and use only 1–2 fonts

**Why it matters**
Each font family and weight is a separate download that can block text rendering (FCP/LCP) or cause layout shift (CLS) when it swaps in. Third-party font CSS adds extra connections.

**Detect**
- Count families and weights: `grep -rnE '@font-face|fonts.googleapis.com|use.typekit.net|next/font|@fontsource' --exclude-dir=node_modules`.
- Google Fonts `<link>` tags loading many weights (`wght@100..900` or long lists).
- Missing `font-display`, missing `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the main body font.
- TTF/OTF files served instead of WOFF2.
- Icon fonts (Font Awesome full sets) used for a handful of icons.
- Lighthouse audits: `font-display`, `render-blocking-resources`, `layout-shift-elements` around text.

**Evidence required**
Number of families and files, total font bytes, which file renders the LCP or body text, and whether it is preloaded.

**Fix**
- Limit to 1–2 families (one for text, at most one for headings) and only the weights in use. Prefer one variable font file over several static weights.
- Self-host WOFF2 files subset to the needed character sets.
  - **Next.js**: `next/font/google` or `next/font/local` self-hosts, preloads, and sets fallback metrics automatically.
  - **Nuxt**: `@nuxt/fonts`. **Astro**: the fonts API or `@fontsource`. **Others**: `@fontsource/*` or download from Google Fonts.
- Preload only the main text font: `<link rel="preload" href="/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>`.
- Set `font-display: swap` (or `optional` for minimal CLS), and use `size-adjust`/`ascent-override` fallback metrics to stop the swap from shifting layout.
- Replace icon fonts with inline SVG or a tree-shaken icon package.

**Verify**
Fewer font requests and bytes; FCP/LCP improve; CLS does not rise; text renders immediately in the filmstrip.

**Pitfalls**
- Preloading more than one or two fonts competes with the LCP image; preload only what the first screen needs.
- The `crossorigin` attribute is required on font preloads or the font downloads twice.
- Do not remove a brand font without the owner's agreement; reduce weights and self-host it instead.

## 3P-01 — Remove third-party scripts you don't need

**Why it matters**
Analytics, chat widgets, tag managers, A/B tools, heatmaps, and embeds often cost more main-thread time than the app itself (TBT/INP) and add connections that delay LCP.

**Detect**
- External scripts: `grep -rnE '<script[^>]+src=["'"'"']https?://' --exclude-dir=node_modules`, plus `next/script`, `useScript`, `@nuxt/scripts`, `<Script>` components, and tag manager containers (whose contents are not in the repo; mark them `needs_measurement`).
- Duplicates: two analytics products doing the same job, or the same tag loaded both directly and through a tag manager.
- Scripts loaded synchronously in `<head>` without `async`/`defer`.
- Heavy embeds (YouTube, Intercom, maps, social feeds) loaded on page load instead of on interaction.
- Lighthouse audits: `third-party-summary`, `bootup-time`, `render-blocking-resources`, `third-party-facades`.

**Evidence required**
Per script: what it is, where it loads, its main-thread time and bytes from Lighthouse `third-party-summary`, and whether something else in the codebase uses it.

**Fix**
- Remove scripts the owner confirms are unused. List candidates and ask; the code cannot show whether marketing still reads a dashboard.
- Load the rest with `defer` or `async`, or with framework strategies: Next.js `<Script strategy="lazyOnload">` (or `afterInteractive`), Nuxt Scripts triggers, Partytown to move tags to a web worker where compatible.
- Use facades for embeds: render a static thumbnail and load the real widget on click (`lite-youtube-embed`, a chat button that loads the widget on first click).
- Add `<link rel="preconnect">` only for third-party origins that are needed before LCP.

**Verify**
Lower TBT and third-party main-thread time; fewer requests before LCP; the remaining tools still record events (check in their debug mode).

**Pitfalls**
- Never remove a consent manager, fraud, payment, or security script without explicit confirmation.
- Deferring analytics can undercount bounces slightly; tell the owner.
- Tag manager contents live outside the repo. Ask the owner to review them rather than guessing.
