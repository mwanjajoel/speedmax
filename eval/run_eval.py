"""Evaluate the speedmax skill running inside Claude Code, with MLflow.

Each case copies a fixture app into a throwaway git workspace, installs the skill as a
project skill, runs `claude -p` headless, converts the session transcript into MLflow
spans, and scores the result with code-based and trace-based scorers plus a Claude judge.

Usage:
    uv run python run_eval.py --group all --model sonnet
    uv run python run_eval.py --group guidance
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import mlflow
from mlflow.entities import Feedback, SpanType, Trace
from mlflow.genai import scorer

from cases import FIX_SEED_FINDINGS, GROUPS
from gen_assets import generate

EVAL_DIR = Path(__file__).resolve().parent
SKILL_DIR = EVAL_DIR.parent
SKILL_FILES = [p for p in SKILL_DIR.iterdir() if p.is_file() and (p.suffix in {".md", ".json"} or p.name == "validate-findings.cjs") and p.name != "README.md"]
VALIDATOR = SKILL_DIR / "validate-findings.cjs"
OUT = ".speedmax-out"

ALLOWED_TOOLS = [
    "Read", "Glob", "Grep", "Write", "Edit", "Skill", "Task", "Agent", "TodoWrite",
    "Bash(ls:*)", "Bash(find:*)", "Bash(grep:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(wc:*)", "Bash(du:*)", "Bash(stat:*)", "Bash(file:*)", "Bash(mkdir:*)", "Bash(node:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)", "Bash(git branch:*)",
    "Bash(git switch:*)", "Bash(git checkout:*)", "Bash(git add:*)", "Bash(git commit:*)", "Bash(git revert:*)",
]
DISALLOWED_TOOLS = ["WebFetch", "WebSearch"]

FORBIDDEN_PROGRAMS = {"npm", "pnpm", "yarn", "bun", "pip", "pip3", "uv", "npx", "lighthouse", "curl", "wget", "next", "vite"}


def forbidden_invocations(command: str) -> list[str]:
    """Programs invoked in command position (heredoc bodies and quoted text are ignored)."""
    lines, body_end = [], None
    for line in command.splitlines():
        if body_end is not None:
            if line.strip() == body_end:
                body_end = None
            continue
        lines.append(line)
        m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if m:
            body_end = m.group(1)
    text = re.sub(r"'[^']*'|\"[^\"]*\"", "''", "\n".join(lines))
    hits = []
    for segment in re.split(r"[;&|\n]+|\$\(", text):
        words = [w for w in segment.split() if not re.match(r"^\w+=", w)]
        if words and words[0].split("/")[-1] in FORBIDDEN_PROGRAMS:
            hits.append(segment.strip())
    return hits


def clean_env() -> dict[str, str]:
    """Strip the host Claude Code session's variables so the child is an independent session."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "MLFLOW_CLAUDE"))}


def git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=ws, capture_output=True, text=True, check=False).stdout


def prepare_workspace(run_root: Path, case_id: str, fixture: str, seed: str | None) -> Path:
    ws = run_root / f"{case_id}-{uuid.uuid4().hex[:6]}"
    shutil.copytree(EVAL_DIR / "fixtures" / fixture, ws)
    generate(fixture, ws)
    with open(ws / ".gitignore", "a") as f:
        f.write(".claude/\n")
    skill_dst = ws / ".claude" / "skills" / "speedmax"
    skill_dst.mkdir(parents=True)
    for p in SKILL_FILES:
        shutil.copy2(p, skill_dst / p.name)
    if seed == "fix":
        out = ws / OUT
        out.mkdir()
        (out / "findings.json").write_text(json.dumps(FIX_SEED_FINDINGS, indent=2))
        checks = {cid: {"status": "applicable", "reason": "seeded for evaluation"} for cid in json.loads((SKILL_DIR / "findings-schema.json").read_text())["items"]["properties"]["check_id"]["enum"]}
        (out / "ledger.json").write_text(json.dumps({"checks": checks}, indent=2))
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "-c", "user.name=eval", "-c", "user.email=eval@example.com", "commit", "-q", "-m", "fixture")
    return ws


def find_transcript(session_id: str) -> Path | None:
    matches = list((Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"))
    return matches[0] if matches else None


def attach_transcript_spans(session_id: str, events: list[dict]) -> None:
    """Turn the Claude Code session into child spans of the current predict_fn span.

    Uses MLflow's own Claude Code transcript converter (the one behind `mlflow autolog claude`),
    falling back to untimed spans from the stream-json events if it is unavailable.
    """
    parent = mlflow.get_current_active_span()
    path = find_transcript(session_id)
    if path is not None:
        try:
            from mlflow.claude_code.tracing import _create_llm_and_tool_spans, read_transcript

            _create_llm_and_tool_spans(parent, read_transcript(str(path)), 0)
            return
        except Exception as e:  # private API; degrade gracefully
            print(f"transcript conversion failed, using stream events: {e}", file=sys.stderr)
    results = {}
    for ev in events:
        if ev.get("type") == "user":
            for block in ev.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    results[block.get("tool_use_id")] = block.get("content")
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for block in ev.get("message", {}).get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                span = mlflow.start_span_no_context(
                    name=f"tool_{block['name']}", parent_span=parent, span_type=SpanType.TOOL, inputs=block.get("input", {})
                )
                span.set_outputs({"result": results.get(block.get("id"))})
                span.end()


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def collect_outputs(ws: Path, result: dict) -> dict:
    out = ws / OUT
    findings_path, ledger_path = out / "findings.json", out / "ledger.json"
    validator_errors = None
    if findings_path.exists():
        cmd = ["node", str(VALIDATOR), str(findings_path)] + ([str(ledger_path)] if ledger_path.exists() else [])
        proc = subprocess.run(cmd, capture_output=True, text=True)
        validator_errors = [line for line in proc.stderr.splitlines() if line.strip()]
    seed_commit = git(ws, "rev-list", "--max-parents=0", "HEAD").strip()
    changed = sorted(set(git(ws, "diff", "--name-only", seed_commit).split() + git(ws, "ls-files", "--others", "--exclude-standard").split()))
    return {
        "final_response": result.get("result", ""),
        "workspace": str(ws),
        "artifacts": sorted(p.name for p in out.iterdir()) if out.exists() else [],
        "findings": read_json(findings_path),
        "ledger": read_json(ledger_path),
        "baseline": read_json(out / "baseline.json"),
        "validator_errors": validator_errors,
        "changed_files": changed,
        "branch": git(ws, "branch", "--show-current").strip(),
        "new_commits": git(ws, "log", "--format=%s", f"{seed_commit}..HEAD").splitlines(),
        "file_contents": {f: (ws / f).read_text() for f in changed if (ws / f).is_file() and (ws / f).stat().st_size < 50_000},
        "permission_denials": result.get("permission_denials", []),
        "num_turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "is_error": result.get("is_error", False),
    }


def make_predict_fn(run_root: Path, model: str, timeout_s: int):
    @mlflow.trace(name="speedmax_skill_run", span_type=SpanType.AGENT)
    def run_skill(case_id: str, fixture: str, prompt: str, seed: str | None = None) -> dict:
        ws = prepare_workspace(run_root, case_id, fixture, seed)
        cmd = [
            "claude", "-p", prompt,
            "--model", model,
            "--output-format", "stream-json", "--verbose",
            "--setting-sources", "project",
            "--allowedTools", *ALLOWED_TOOLS,
            "--disallowedTools", *DISALLOWED_TOOLS,
        ]
        started = time.time()
        proc = subprocess.run(cmd, cwd=ws, env=clean_env(), capture_output=True, text=True, timeout=timeout_s, stdin=subprocess.DEVNULL)
        events = []
        for line in proc.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        (ws.parent / f"{ws.name}.stream.jsonl").write_text(proc.stdout)
        result = next((e for e in reversed(events) if e.get("type") == "result"), {"result": proc.stderr[-2000:], "is_error": True})
        if result.get("session_id"):
            attach_transcript_spans(result["session_id"], events)
        outputs = collect_outputs(ws, result)
        outputs["wall_seconds"] = round(time.time() - started)
        return outputs

    return run_skill


# ---------------------------------------------------------------- helpers for scorers

def tool_spans(trace: Trace, name: str | None = None):
    spans = [s for s in trace.data.spans if s.span_type == SpanType.TOOL]
    if name:
        spans = [s for s in spans if s.name == f"tool_{name}"]
    return sorted(spans, key=lambda s: s.start_time_ns)


def bash_commands(trace: Trace) -> list[str]:
    return [str((s.inputs or {}).get("command", "")) for s in tool_spans(trace, "Bash")]


def findings_of(outputs) -> list[dict]:
    f = outputs.get("findings")
    return f if isinstance(f, list) else []


def source_changes(outputs) -> list[str]:
    return [f for f in outputs.get("changed_files", []) if not f.startswith((OUT + "/", ".claude/"))]


# ---------------------------------------------------------------- shared scorers

@scorer
def findings_valid(outputs) -> Feedback:
    """findings.json exists and passes validate-findings.cjs (including the ledger)."""
    errs = outputs.get("validator_errors")
    if errs is None:
        return Feedback(value=False, rationale=f"no {OUT}/findings.json written; artifacts={outputs.get('artifacts')}")
    return Feedback(value=not errs, rationale="validator passed" if not errs else "; ".join(errs[:8]))


@scorer
def no_installs_or_network(trace: Trace, outputs) -> Feedback:
    """No package installs, builds, Lighthouse/npx, or network calls were attempted (allowed or denied)."""
    bad = [hit for c in bash_commands(trace) for hit in forbidden_invocations(c)]
    bad += [hit for d in outputs.get("permission_denials", []) for hit in forbidden_invocations(str((d.get("tool_input") or {}).get("command", "")))]
    return Feedback(value=not bad, rationale="none attempted" if not bad else f"attempted: {bad[:5]}")


# ---------------------------------------------------------------- audit scorers

@scorer
def ledger_complete(outputs) -> Feedback:
    """ledger.json decides all 18 checks."""
    ledger = outputs.get("ledger") or {}
    n = len((ledger.get("checks") or {}))
    return Feedback(value=n == 18, rationale=f"{n}/18 checks in ledger")


@scorer
def no_source_edits(outputs) -> Feedback:
    """An audit must not change source before approval."""
    changed = source_changes(outputs)
    return Feedback(value=not changed, rationale="source untouched" if not changed else f"changed: {changed}")


@scorer
def stops_at_approval_gate(outputs) -> Feedback:
    """Every finding is still 'proposed' and the final message asks which findings to apply."""
    statuses = {f.get("status") for f in findings_of(outputs)}
    asks = bool(re.search(r"approv|which [\w\s-]{0,30}(to )?(apply|fix)|want me to apply|apply (any|which)|tell me which", outputs.get("final_response", ""), re.I))
    ok = statuses <= {"proposed"} and asks
    return Feedback(value=ok, rationale=f"statuses={sorted(s for s in statuses if s)}, asks_for_approval={asks}")


@scorer
def measure_first(trace: Trace) -> Feedback:
    """Baseline/run metadata (measurement or recorded measurement gap) is written before findings.json."""
    writes = [(s.start_time_ns, str((s.inputs or {}).get("file_path", ""))) for s in tool_spans(trace, "Write")]
    first = lambda pat: next((t for t, p in writes if re.search(pat, p)), None)  # noqa: E731
    baseline_t, findings_t = first(r"(baseline|run-metadata)\.json$"), first(r"findings\.json$")
    if findings_t is None:
        return Feedback(value=False, rationale="findings.json never written")
    ok = baseline_t is not None and baseline_t <= findings_t
    return Feedback(value=ok, rationale=f"baseline/run-metadata written {'before' if ok else 'after or never before'} findings.json")


@scorer
def no_fabricated_metrics(outputs) -> Feedback:
    """Lighthouse could not run, so no finding or baseline may carry Lighthouse numbers."""
    fake = [f["id"] for f in findings_of(outputs) if re.search(r"lighthouse|pagespeed|psi", str((f.get("evidence") or {}).get("tool", "")), re.I) and isinstance((f.get("evidence") or {}).get("baseline"), (int, float))]
    base = outputs.get("baseline") or {}
    route_numbers = [r for r, v in (base.get("routes") or {}).items() if isinstance(v, dict) and any(isinstance(x, (int, float)) for x in (v.get("median") or {}).values())]
    bad = fake + [f"baseline route {r}" for r in route_numbers]
    return Feedback(value=not bad, rationale="no invented lab metrics" if not bad else f"numbers without a measurement: {bad}")


@scorer
def planted_recall(outputs, expectations) -> Feedback:
    """Fraction of planted issues reported (confirmed or needs_measurement)."""
    planted = expectations["planted_check_ids"]
    found = {f.get("check_id") for f in findings_of(outputs) if f.get("verdict") in ("confirmed", "needs_measurement")}
    missed = [c for c in planted if c not in found]
    return Feedback(value=round((len(planted) - len(missed)) / len(planted), 3), rationale=f"missed: {missed}" if missed else "all planted issues found")


@scorer
def lcp_image_handled(outputs) -> Feedback:
    """The lazy-loaded hero (LCP) image is flagged with a priority/eager fix, never 'add lazy'."""
    hits = [f for f in findings_of(outputs) if f.get("check_id") == "IMG-02" and re.search(r"hero|lcp", json.dumps(f), re.I)]
    good = [f for f in hits if re.search(r"fetchpriority|priority|eager|remove[^.]{0,40}lazy|not[^.]{0,20}lazy", json.dumps(f.get("fix", {})) + f.get("title", ""), re.I)]
    return Feedback(value=bool(good), rationale=f"{len(hits)} IMG-02 findings mention the hero; {len(good)} prescribe eager/priority loading")


@scorer
def no_false_positives(outputs, expectations) -> Feedback:
    """On an already-optimized site, nothing in must_not_confirm is reported as confirmed."""
    bad = [f"{f.get('id')}:{f.get('check_id')}" for f in findings_of(outputs) if f.get("verdict") == "confirmed" and f.get("check_id") in expectations["must_not_confirm"]]
    return Feedback(value=not bad, rationale="no false positives" if not bad else f"confirmed on a clean site: {bad}")


@scorer
def not_applicable_marked(outputs, expectations) -> Feedback:
    """Checks with nothing to inspect (no DB, no AI, no search) are marked not_applicable in the ledger."""
    checks = ((outputs.get("ledger") or {}).get("checks") or {})
    wrong = [c for c in expectations["expected_not_applicable"] if (checks.get(c) or {}).get("status") != "not_applicable"]
    return Feedback(value=not wrong, rationale="all marked not_applicable" if not wrong else f"not marked n/a: {wrong}")


# ---------------------------------------------------------------- guidance scorers

@scorer
def guidance_no_artifacts(outputs) -> Feedback:
    """Guidance mode writes no audit artifacts and edits no source."""
    bad = outputs.get("artifacts", []) + source_changes(outputs)
    return Feedback(value=not bad, rationale="nothing written" if not bad else f"wrote: {bad}")


@scorer
def cites_locations(outputs, expectations) -> Feedback:
    """The answer points at the relevant files."""
    text = outputs.get("final_response", "")
    missing = [f for f in expectations["expected_files"] if f not in text and Path(f).name not in text]
    return Feedback(value=not missing, rationale="cites expected files" if not missing else f"missing: {missing}")


def claude_judge(rubric: str, question: str, answer: str, model: str = "haiku") -> tuple[bool, str]:
    prompt = (
        "You are grading an AI coding assistant's answer against a rubric. Do not use any tools.\n\n"
        f"RUBRIC:\n{rubric}\n\nQUESTION:\n{question}\n\nANSWER:\n{answer}\n\n"
        'Reply with only a JSON object: {"pass": true|false, "rationale": "<one or two sentences>"}'
    )
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--output-format", "json", "--setting-sources", "project", "--disallowedTools", "Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"],
            cwd=tmp, env=clean_env(), capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
        )
    text = json.loads(proc.stdout).get("result", "")
    m = re.search(r"\{.*\}", text, re.S)
    verdict = json.loads(m.group(0)) if m else {"pass": False, "rationale": f"unparseable judge output: {text[:200]}"}
    return bool(verdict.get("pass")), verdict.get("rationale", "")


@scorer
def guidance_quality(inputs, outputs, expectations) -> Feedback:
    """LLM judge (Claude Haiku via Claude Code CLI) grades the answer against the case rubric."""
    ok, why = claude_judge(expectations["rubric"], inputs["prompt"], outputs.get("final_response", ""))
    return Feedback(value=ok, rationale=why, source=mlflow.entities.AssessmentSource(source_type="LLM_JUDGE", source_id="claude-haiku"))


# ---------------------------------------------------------------- fix scorers

@scorer
def applied_only_approved(outputs, expectations) -> Feedback:
    """Only the approved finding's files changed."""
    changed = source_changes(outputs)
    missing = [f for f in expectations["must_change"] if f not in changed]
    forbidden = [f for f in expectations["must_not_change"] if f in changed]
    ok = not missing and not forbidden
    return Feedback(value=ok, rationale=f"changed={changed}; missing={missing}; out_of_scope={forbidden}")


@scorer
def n_plus_one_fixed(outputs) -> Feedback:
    """The orders route eager-loads customers instead of querying inside the loop."""
    src = (outputs.get("file_contents") or {}).get("app/api/orders/route.ts", "")
    ok = bool(re.search(r"include\s*:\s*\{\s*customer", src)) and "findUnique" not in src
    return Feedback(value=ok, rationale="include: { customer } and no per-order findUnique" if ok else "route still queries per order or file unchanged")


@scorer
def branch_and_commit(outputs) -> Feedback:
    """Fix lands on a new branch in a commit that names the finding."""
    branch, commits = outputs.get("branch"), outputs.get("new_commits", [])
    ok = branch not in ("main", "master", "") and any("F-001" in c for c in commits)
    return Feedback(value=ok, rationale=f"branch={branch!r}, commits={commits}")


@scorer
def status_tracked(outputs) -> Feedback:
    """F-001 becomes 'applied' (not 'verified': nothing could be re-measured); F-002 stays 'proposed'."""
    by_id = {f.get("id"): f.get("status") for f in findings_of(outputs)}
    ok = by_id.get("F-001") == "applied" and by_id.get("F-002") == "proposed"
    return Feedback(value=ok, rationale=f"statuses={by_id}")


SCORERS = {
    "audit_planted": [findings_valid, ledger_complete, no_source_edits, stops_at_approval_gate, measure_first, no_fabricated_metrics, no_installs_or_network, planted_recall, lcp_image_handled],
    "audit_clean": [findings_valid, ledger_complete, no_source_edits, stops_at_approval_gate, measure_first, no_fabricated_metrics, no_installs_or_network, no_false_positives, not_applicable_marked],
    "guidance": [guidance_no_artifacts, cites_locations, guidance_quality, no_installs_or_network],
    "fix": [applied_only_approved, n_plus_one_fixed, branch_and_commit, status_tracked, findings_valid, no_installs_or_network],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default="all", choices=["all", *GROUPS])
    ap.add_argument("--model", default="sonnet", help="model alias or ID passed to claude --model")
    ap.add_argument("--tracking-uri", default=os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{EVAL_DIR / 'mlflow.db'}"))
    ap.add_argument("--experiment", default="speedmax-skill-eval")
    ap.add_argument("--timeout", type=int, default=2400, help="seconds per case")
    args = ap.parse_args()
    # MLflow otherwise runs the first case an extra time to check tracing; each case is a long, paid agent run.
    os.environ.setdefault("MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION", "true")

    mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experiment)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    groups = list(GROUPS) if args.group == "all" else [args.group]

    for group in groups:
        run_root = EVAL_DIR / ".runs" / f"{stamp}-{group}"
        run_root.mkdir(parents=True)
        with mlflow.start_run(run_name=f"{group}-{args.model}-{stamp}"):
            mlflow.log_params({"group": group, "agent_model": args.model, "judge_model": "haiku", "cases": len(GROUPS[group])})
            result = mlflow.genai.evaluate(data=GROUPS[group], predict_fn=make_predict_fn(run_root, args.model, args.timeout), scorers=SCORERS[group])
        print(f"\n== {group} ==")
        for k, v in sorted(result.metrics.items()):
            print(f"  {k}: {v}")
        print(f"  workspaces: {run_root}")


if __name__ == "__main__":
    main()
