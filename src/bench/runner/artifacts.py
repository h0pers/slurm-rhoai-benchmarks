"""Per-run artifact directory: result.json, pod logs, events.

Layout produced for every benchmark run:

    results/<scenario>/<run-id>/
        result.json     # machine-readable outcome (schema below)
        events.json     # namespace events observed during the run
        logs/<pod>.log  # container logs per pod

result.json fields (timestamps are ISO-8601 UTC):
    schema_version, scenario, run_id,
    config       - snapshot of the scenario definition used
    config_hash  - sha256 of the snapshot, to prove two runs used one config
    versions     - cluster/component versions captured at run time
    timestamps   - submitted / admitted / pods_running / completed / ...
    durations_s  - queue, startup, training, total (derived from timestamps)
    metrics      - throughput, GPU utilization, scenario-specific numbers
    passed       - overall verdict, failures - list of criteria that failed
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bench.config import settings
from bench.utils import durations

SCHEMA_VERSION = "1.0"

# Adjacent timestamp pairs from which phase durations are derived.
PHASES = {
    "queue": ("submitted", "admitted"),
    "startup": ("admitted", "pods_running"),
    "training": ("pods_running", "completed"),
    "total": ("submitted", "completed"),
}


def new_run_dir(scenario_name: str) -> Path:
    run_id = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    run_dir = settings.results_dir / scenario_name / run_id
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    return run_dir


def write_result(
    run_dir: Path,
    config: dict,
    versions: dict,
    timestamps: dict[str, str],
    metrics: dict[str, Any],
    passed: bool,
    failures: list[str],
    notes: str = "",
) -> Path:
    result = {
        "schema_version": SCHEMA_VERSION,
        "scenario": run_dir.parent.name,
        "run_id": run_dir.name,
        "config": config,
        "config_hash": hashlib.sha256(
            json.dumps(config, sort_keys=True, default=str).encode(),
        ).hexdigest()[:12],
        "versions": versions,
        "timestamps": timestamps,
        "durations_s": durations(timestamps, PHASES),
        "metrics": metrics,
        "passed": passed,
        "failures": failures,
        "notes": notes,
    }
    path = run_dir / "result.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return path


def write_events(run_dir: Path, events: list[dict]) -> None:
    (run_dir / "events.json").write_text(json.dumps(events, indent=2, default=str) + "\n")


def write_log(run_dir: Path, pod: str, content: str) -> None:
    (run_dir / "logs" / (pod + ".log")).write_text(content)
