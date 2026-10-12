"""Evaluation dataset for the speedmax skill.

Each group is evaluated separately because its scorers only make sense for that mode.
"""

NON_INTERACTIVE = (
    "This is a non-interactive run: you cannot ask me questions and nobody will answer. "
    "You may not install packages, start servers, run builds, or contact network services; "
    "record anything you cannot measure the way the skill tells you to."
)

ALL_PLANTED = [
    "IMG-01", "IMG-02", "FONT-01", "3P-01", "DEP-01", "JS-01", "UX-03",
    "DB-01", "DB-02", "DB-03", "CACHE-01", "JOB-01", "UX-01", "UX-02",
]

# Seed for the fix-mode case: one approved finding and one that is only proposed.
FIX_SEED_FINDINGS = [
    {
        "id": "F-001",
        "check_id": "DB-02",
        "title": "GET /api/orders runs one customer query per order (N+1)",
        "verdict": "confirmed",
        "impact": "high",
        "effort": "S",
        "routes": ["/api/orders", "/dashboard"],
        "locations": ["app/api/orders/route.ts:7-11"],
        "mechanism": "findUnique for each order inside a for loop; queries grow with the number of orders.",
        "evidence": {"tool": "source", "metric": "queries_per_request", "baseline": None, "estimate": "1 + N queries for N orders"},
        "fix": {"summary": "Eager-load the customer with include: { customer: true } in the findMany call and drop the loop.", "files": ["app/api/orders/route.ts"]},
        "status": "approved",
    },
    {
        "id": "F-002",
        "check_id": "UX-01",
        "title": "Assistant response is not streamed",
        "verdict": "confirmed",
        "impact": "high",
        "effort": "M",
        "routes": ["/dashboard"],
        "locations": ["app/api/chat/route.ts:10", "components/Chat.tsx:11"],
        "mechanism": "messages.create without streaming; the client awaits res.json().",
        "evidence": {"tool": "source", "metric": "time_to_first_token_ms", "baseline": None, "estimate": "full generation time (5-15 s) before any text"},
        "fix": {"summary": "Use client.messages.stream on the server, return an SSE stream, and read it incrementally in Chat.tsx.", "files": ["app/api/chat/route.ts", "components/Chat.tsx"]},
        "status": "proposed",
    },
]

GROUPS = {
    "audit_planted": [
        {
            "inputs": {
                "case_id": "audit-slow-shop",
                "fixture": "slow-shop",
                "seed": None,
                "prompt": (
                    "Run a full speedmax performance audit of this repository. "
                    "Write the run artifacts to ./.speedmax-out (it is git-ignored). " + NON_INTERACTIVE
                ),
            },
            "expectations": {"planted_check_ids": ALL_PLANTED},
        },
    ],
    "audit_clean": [
        {
            "inputs": {
                "case_id": "audit-lean-site",
                "fixture": "lean-site",
                "seed": None,
                "prompt": (
                    "Run a full speedmax performance audit of this repository. "
                    "Write the run artifacts to ./.speedmax-out (it is git-ignored). " + NON_INTERACTIVE
                ),
            },
            "expectations": {
                "must_not_confirm": ["IMG-01", "IMG-02", "FONT-01", "3P-01", "DEP-01", "CDN-01", "UX-01", "DB-01", "DB-02", "DB-03", "JOB-01", "CACHE-01", "UX-03"],
                "expected_not_applicable": ["DB-01", "DB-02", "DB-03", "UX-01", "UX-03"],
            },
        },
    ],
    "guidance": [
        {
            "inputs": {
                "case_id": "guidance-lazy-images",
                "fixture": "slow-shop",
                "seed": None,
                "prompt": "Quick question, not an audit: should I just add loading=\"lazy\" to every image on the home page to make it faster?",
            },
            "expectations": {
                "rubric": (
                    "PASS only if the answer (1) says the hero / above-the-fold / LCP image must NOT be lazy-loaded, "
                    "(2) notices the hero image in app/page.tsx is currently lazy and recommends removing that and/or "
                    "adding fetchpriority=\"high\" or equivalent priority, and (3) says lazy-loading the below-the-fold "
                    "gallery images (and ideally the iframe) is good. FAIL if it recommends lazy-loading every image."
                ),
                "expected_files": ["app/page.tsx"],
            },
        },
        {
            "inputs": {
                "case_id": "guidance-slow-chat",
                "fixture": "slow-shop",
                "seed": None,
                "prompt": "The assistant on the dashboard feels really slow; users stare at 'Thinking…' for about ten seconds. What should I change? Don't edit anything yet.",
            },
            "expectations": {
                "rubric": (
                    "PASS only if the answer recommends streaming the response end to end: a streaming call on the "
                    "server (e.g. messages.stream or stream: true), a streaming HTTP response (e.g. SSE), and incremental "
                    "reading in the client instead of res.json(). Extra credit (not required) for noticing that every "
                    "order is loaded into the prompt with an unbounded findMany. FAIL if it only suggests a spinner, "
                    "a faster model, or caching."
                ),
                "expected_files": ["app/api/chat/route.ts", "components/Chat.tsx"],
            },
        },
        {
            "inputs": {
                "case_id": "guidance-orders-scale",
                "fixture": "slow-shop",
                "seed": None,
                "prompt": "Will GET /api/orders stay fast as we grow to thousands of orders per customer? Just tell me, don't change code.",
            },
            "expectations": {
                "rubric": (
                    "PASS only if the answer identifies all three: (1) the N+1 customer lookup inside the loop and an "
                    "eager-load/include fix, (2) the missing index on Order.userId (ideally composite with status/createdAt) "
                    "delivered as a migration, and (3) the unbounded findMany needing pagination (cursor preferred). "
                    "FAIL if any of the three is missing."
                ),
                "expected_files": ["app/api/orders/route.ts", "prisma/schema.prisma"],
            },
        },
    ],
    "fix": [
        {
            "inputs": {
                "case_id": "fix-approved-only",
                "fixture": "slow-shop",
                "seed": "fix",
                "prompt": (
                    "Apply the approved speedmax findings in ./.speedmax-out/findings.json (ledger is next to it). "
                    + NON_INTERACTIVE
                ),
            },
            "expectations": {
                "must_change": ["app/api/orders/route.ts"],
                "must_not_change": ["app/api/chat/route.ts", "components/Chat.tsx"],
            },
        },
    ],
}
