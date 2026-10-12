# Evaluating speedmax with MLflow

This follows MLflow's [Evaluating and Improving Agent Skills](https://mlflow.org/blog/evaluating-improving-agent-skills/) loop: run the skill on a dataset, trace every step, score outcomes and behavior, inspect failing traces, update the skill, and re-run.

## How it works

1. **Dataset** (`cases.py`). Six cases in four groups:
   - `audit_planted`: a full audit of `fixtures/slow-shop`, a Next.js + Prisma app with 14 planted issues.
   - `audit_clean`: a full audit of `fixtures/lean-site`, an already-optimized static site, to catch false positives.
   - `guidance`: three focused questions (lazy-loading, slow AI chat, orders endpoint at scale).
   - `fix`: apply one approved finding while leaving a proposed one alone.
2. **Agent run** (`predict_fn`):
   - Each case copies its fixture into a throwaway git workspace under `.runs/`.
   - It installs the skill as a project skill and runs `claude -p` headless.
   - Tools are restricted by an allowlist: read-only shell commands, git, file edits, and `node` only for the skill's validator. Web tools are disallowed. Denied attempts are still recorded.
   - The agent gets an allowlisted environment (`PATH`, `HOME`, locale, and `ANTHROPIC_*` for authentication), not your full shell environment.
   - Fixtures are copied without symlinks or agent configuration (`.claude/`, `.mcp.json`, `CLAUDE.md`), and the workspace's `.claude/` is made read-only so the agent can't edit the validator or add settings.
   - This is not an OS sandbox: the agent still runs as you. Run the eval on a machine where that is acceptable.
3. **Tracing.** The Claude Code session transcript is converted into MLflow spans, one per LLM turn and tool call, using MLflow's own converter (the one behind `mlflow autolog claude`). The spans nest under the `speedmax_skill_run` trace that `mlflow.genai.evaluate` scores.
4. **Scorers.** All of these are custom `@scorer` functions:

| Scorer | Kind | What it checks |
|---|---|---|
| `findings_valid` | output | `findings.json` + `ledger.json` pass `validate-findings.cjs` |
| `ledger_complete` | output | all 18 checks decided |
| `no_source_edits` | output | audit leaves source untouched |
| `stops_at_approval_gate` | output | findings stay `proposed`; the agent asks what to apply |
| `measure_first` | trace | baseline/run metadata written before findings |
| `no_fabricated_metrics` | output | no Lighthouse numbers when Lighthouse never ran |
| `no_installs_or_network` | trace | no installs, builds, `npx`, `curl`, or Lighthouse attempts |
| `planted_recall` | output | share of the 14 planted issues reported |
| `lcp_image_handled` | output | the lazy hero image gets an eager/priority fix |
| `no_false_positives` | output | nothing confirmed on the clean site |
| `not_applicable_marked` | output | no-DB / no-AI checks marked `not_applicable` |
| `guidance_no_artifacts` | output | guidance answers write nothing |
| `cites_locations` | output | the answer names the relevant files |
| `guidance_quality` | LLM judge | Claude Haiku grades the answer against the case rubric |
| `applied_only_approved` | output | fix mode touches only the approved finding's files |
| `n_plus_one_fixed` | output | the orders route eager-loads customers |
| `branch_and_commit` | output | the fix is on a new branch, in a commit naming `F-001` |
| `status_tracked` | output | `F-001` → `applied`, `F-002` stays `proposed` |

## Run

```bash
cd eval
uv sync --locked --python 3.12
uv run mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5055
```

In another shell:

```bash
MLFLOW_TRACKING_URI=http://127.0.0.1:5055 uv run python run_eval.py --group all --model sonnet
```

Open http://127.0.0.1:5055, then **Experiments → speedmax-skill-eval → Evaluations**.

Notes:
- The agent and the judge run through your logged-in Claude Code CLI, so runs use your Claude plan or API credits. A full audit case typically takes 5–20 minutes.
- Each workspace stays in `.runs/<stamp>-<group>/<case>/` with the raw `stream-json` next to it, so a failing case can be inspected end to end. Its `.claude/` is read-only; to delete old runs, use `chmod -R u+w .runs && rm -rf .runs`.
- Unit tests for the harness's containment helpers run without an agent: `uv run python -m unittest test_run_eval`.
- Results vary between runs. Repeat a group 2–3 times before drawing conclusions from a single failure.
