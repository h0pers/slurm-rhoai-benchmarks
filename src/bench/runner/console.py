"""Structured console output for benchmark runs."""

from datetime import UTC, datetime
from typing import Any

from rich.console import Console

from bench.runner import criteria, jobs
from bench.schemas import GangScenario, PreemptionScenario, TrainScenario

Scenario = TrainScenario | GangScenario | PreemptionScenario

_PHASE_DURATIONS = {
    "admitted": ("submitted", "admitted", "queue"),
    "pods_running": ("admitted", "pods_running", "startup"),
    "completed": ("pods_running", "completed", "training"),
}


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def log(console: Console, phase: str, detail: str) -> None:
    line = f"{_now()}  {phase:<20s} {detail}"
    console.print(line)


def log_phases(console: Console, timestamps: dict, logged: set[str]) -> None:
    for key, (start_key, end_key, label) in _PHASE_DURATIONS.items():
        if key in timestamps and key not in logged:
            logged.add(key)
            start, end = timestamps.get(start_key), timestamps.get(end_key)
            duration = ""
            if start and end:
                secs = jobs.seconds_between(start, end)
                duration = f"{label}: {secs}s"
            if key == "completed" and "submitted" in timestamps:
                total = jobs.seconds_between(timestamps["submitted"], timestamps["completed"])
                duration += f"  total: {total}s"
            log(console, key.replace("_", " ").capitalize(), duration)

    if "failed" in timestamps and "failed" not in logged:
        logged.add("failed")
        log(console, "Failed", "")


def print_header(scenario: Scenario, console: Console) -> None:
    console.rule()
    console.print(f" {scenario.name} ({scenario.kind})")
    console.print(f" {scenario.description}")
    if isinstance(scenario, TrainScenario):
        gpus = scenario.resources_per_node.get("nvidia.com/gpu", 0)
        console.print(
            f" {scenario.nodes} node(s), {gpus} GPU(s),"
            f" {scenario.training.max_steps} steps, timeout {scenario.timeout_s}s",
        )
    console.rule()


def print_metrics(metrics: dict[str, Any], console: Console) -> None:
    if not metrics:
        return
    console.print()
    console.rule("Metrics", align="left")
    for key, value in metrics.items():
        if value is not None:
            console.print(f"  {key:<30s} {value}")


def print_checks(
    checks: list[str],
    timestamps: dict,
    metrics: dict,
    scenario: Scenario,
    console: Console,
) -> None:
    console.print()
    console.rule("Checks", align="left")
    for name in checks:
        fn = criteria.REGISTRY[name]
        result = fn(timestamps, metrics, scenario)
        if result is None:
            console.print(f"  PASS  {name}")
        else:
            console.print(f"  FAIL  {name:<30s} {result}")


def print_footer(passed: bool, failures: list[str], run_dir: Any, console: Console) -> None:
    console.print()
    verdict = "PASS" if passed else "FAIL"
    console.print(f"{verdict}  {run_dir}")
    if failures:
        console.print("  " + "; ".join(failures))
