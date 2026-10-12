"""Re-scores the latest finished run of a group from its stored traces, without re-running the agent.

Usage: uv run python rescore.py audit_planted fix
"""
import sys

import mlflow

from run_eval import SCORERS

mlflow.set_tracking_uri("http://127.0.0.1:5055")
mlflow.set_experiment("speedmax-skill-eval")
exp = mlflow.get_experiment_by_name("speedmax-skill-eval")
for group in sys.argv[1:]:
    run = mlflow.search_runs([exp.experiment_id], filter_string=f"params.group = '{group}' and attributes.status = 'FINISHED'", order_by=["attributes.start_time DESC"], max_results=1).iloc[0]
    traces = mlflow.search_traces(locations=[exp.experiment_id], run_id=run["run_id"])
    with mlflow.start_run(run_name=f"{group}-rescored-from-{run['run_id'][:8]}"):
        mlflow.log_params({"group": group, "rescored_from": run["run_id"], "agent_model": run.get("params.agent_model")})
        result = mlflow.genai.evaluate(data=traces, scorers=SCORERS[group])
    print(f"\n== {group} (rescored) ==")
    for k, v in sorted(result.metrics.items()):
        print(f"  {k}: {v}")
