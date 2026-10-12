# Perceived Performance

#### When to use this file

Use this file when users wait for something they can see: AI responses, data loading, route transitions. These checks do not always change lab metrics much, but they decide whether the product feels fast. Checks: **UX-01, UX-02**.

## Core discipline (include in every agent prompt for this domain)

```
- A finding names the screen or endpoint, what the user sees while waiting (blank, spinner, frozen UI, layout jump), and for how long.
- Streaming must work end to end: model SDK → server handler → transport → client renderer. A break anywhere buffers the whole response.
- Loading states must reserve the final layout's size. A skeleton that causes layout shift is a CLS regression.
- Do not fake speed by hiding content that has loaded, or by showing results that are not real.
- Return structured candidates. Do not edit source.
```

## UX-01 — Stream AI responses instead of waiting for the full answer

**Why it matters**
A large-model answer can take 5–30 seconds to finish, but the first tokens arrive in under a second. Without streaming, users stare at a spinner for the full duration. With streaming, the time to first visible text drops to roughly the model's time to first token.

**Detect**
- Non-streaming SDK calls on user-facing paths:
  - Anthropic: `client.messages.create({...})` without `stream: true` (or not using `client.messages.stream(...)`).
  - OpenAI-compatible: `chat.completions.create` / `responses.create` without `stream: true`.
  - Vercel AI SDK: `generateText`/`generateObject` where `streamText`/`streamObject` fits.
  - LangChain: `.invoke()` where `.stream()` fits.
  - Python: `client.messages.create(...)` without `stream=True` or the `client.messages.stream(...)` context manager.
- Streaming broken in the middle:
  - Server handlers that collect chunks into a string and then return JSON.
  - Responses buffered by compression or a proxy (missing `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` behind nginx).
  - Serverless runtimes or adapters that do not support streaming responses on the current configuration.
  - Client code that calls `await res.json()` instead of reading `res.body` with a reader or using a streaming hook.
- Baseline `ai` entry: time to first token vs time to full response.

**Evidence required**
The route, the call site, measured or estimated time to full response, and where the stream is lost (SDK, server, transport, or client).

**Fix**
- Server:
  - Anthropic TypeScript: `const stream = client.messages.stream({...}); for await (const event of stream) { ... }` and forward text deltas.
  - Vercel AI SDK: `streamText({...})` and `return result.toUIMessageStreamResponse()` (or the response helper for the installed SDK version).
  - Python (FastAPI/Starlette): `StreamingResponse(generator(), media_type="text/event-stream")`; Django: `StreamingHttpResponse`; Rails: `ActionController::Live`; Laravel: `response()->stream()` / `->eventStream()`.
- Transport: Server-Sent Events with `Content-Type: text/event-stream`, `Cache-Control: no-cache`, no compression buffering; disable proxy buffering.
- Client: `useChat`/`useCompletion` (AI SDK), or `res.body.getReader()` + `TextDecoder` appending to state; render Markdown incrementally; auto-scroll; offer a Stop button wired to `AbortController`.
- For structured output the UI needs whole, stream partial objects (`streamObject`) or show progress steps instead.

**Verify**
Time to first visible token drops to about the model's time to first token (usually under 1–2 s); the full response still renders correctly; Stop cancels the upstream request.

**Pitfalls**
- Tool-use and agent loops may pause between steps; show step status rather than a frozen stream.
- Do not stream into a component that re-renders the whole Markdown tree on every token for long answers; throttle updates (for example every animation frame).
- Persist the final message after the stream completes, and handle client disconnects so partial answers are not saved as complete.

## UX-02 — Show skeletons and loading states, not blank screens

**Why it matters**
Blank screens during data loading feel broken and slower than they are. Content popping in without reserved space causes layout shift (CLS), which is a Core Web Vital.

**Detect**
- Components that render `null`/nothing while loading: `if (!data) return null`, `{data && <List/>}` with no else branch, `v-if="data"` without `v-else`.
- Missing route-level loading UI: Next.js App Router routes without `loading.tsx` or `<Suspense fallback>` around slow server components; Nuxt `useFetch` without `pending` handling; SvelteKit pages without streamed promises or `{#await}` states; Remix `defer` without `<Await>` fallbacks.
- Buttons that start async work with no pending state (double submits, frozen feel).
- Lighthouse audits: `layout-shift-elements`, `cumulative-layout-shift`; the filmstrip shows empty frames.

**Evidence required**
The screen, what renders during the wait (screenshot or description), the wait duration, and any measured CLS caused by late content.

**Fix**
- Skeletons that match the final layout's dimensions: same height rows, card sizes, and image `aspect-ratio`. Use `min-height` on containers that fill asynchronously.
- Route-level: Next.js `loading.tsx` or `<Suspense fallback={<Skeleton/>}>` around each slow section (streaming SSR); Nuxt `<NuxtLoadingIndicator>` + `pending` UI; SvelteKit streaming with `{#await}`; React Router `HydrateFallback`/`defer`.
- Button pending states: disable and show a spinner or label change while submitting (`useFormStatus`, `isPending`, `aria-busy`).
- Optimistic updates for quick mutations (TanStack Query `onMutate`, React `useOptimistic`), with rollback on error.
- Error states next to loading states, so a failed request does not leave a skeleton forever.
- Avoid a full-page spinner; show the shell (header, navigation) immediately and load the sections.

**Verify**
The filmstrip shows content structure from the first frames; CLS stays at or below 0.1; screen readers announce loading (`aria-busy`, `role="status"`).

**Pitfalls**
- Skeletons with the wrong size cause CLS when real content replaces them.
- Do not show a skeleton for very fast loads (< 200–300 ms); a short delay before showing it avoids flicker.
- A skeleton is not a fix for a slow query. Fix the cause too (DB-01, DB-02, CACHE-01).
