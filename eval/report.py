"""Prints per-case scorer values and rationales for the latest run of each eval group."""
import sys

import mlflow

def printable(text: str) -> str:
    """Rationales can carry agent-written text; drop control characters before they reach the terminal."""
    return "".join(c if c.isprintable() else " " for c in text)


mlflow.set_tracking_uri(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5055")
exp = mlflow.get_experiment_by_name("speedmax-skill-eval")
runs = mlflow.search_runs([exp.experiment_id], filter_string="attributes.status = 'FINISHED'", order_by=["attributes.start_time DESC"])
seen = set()
for _, run in runs.iterrows():
    group = run.get("params.group")
    if not group or group in seen:
        continue
    seen.add(group)
    print(f"\n=== {group} ({run['run_id'][:8]}) ===")
    for t in mlflow.search_traces(locations=[exp.experiment_id], run_id=run["run_id"], return_type="list"):
        req = t.data.request or ""
        case = next((c for c in ["audit-slow-shop", "audit-lean-site", "guidance-lazy-images", "guidance-slow-chat", "guidance-orders-scale", "fix-approved-only"] if c in req), "?")
        print(f"-- {case}")
        for a in sorted(t.info.assessments, key=lambda a: a.name):
            if a.feedback is None:
                continue
            print(f"   {a.name:24} {str(a.feedback.value):6} {printable((a.rationale or '')[:300])}")
