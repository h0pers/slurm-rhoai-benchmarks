"""Preemption scenario flow (workload class 6)."""

import time
from pathlib import Path
from typing import Any

from rich.console import Console

from bench.config import settings
from bench.runner import artifacts, criteria, jobs, kube
from bench.schemas import PreemptionScenario
from bench.utils import utcnow


def run_preemption(
    scenario: PreemptionScenario,
    run_dir: Path,
    console: Console,
    log_fn: Any,
    log_phases_fn: Any,
) -> tuple[bool, list[str], dict[str, Any], dict[str, Any]]:
    low = jobs.submit_hold(scenario.low_priority, scenario, "low")
    log_fn(console, "Low-priority submitted", low)

    deadline = time.monotonic() + scenario.timeout_s
    _wait_for_pods(
        low, scenario.low_priority.nodes, deadline, console, "Low-priority running", log_fn
    )

    wait_s = scenario.high_priority.submit_after_s or 0
    if wait_s:
        console.print(f"  waiting {wait_s}s before high-priority submission...")
        time.sleep(wait_s)

    high = jobs.submit_hold(scenario.high_priority, scenario, "high")
    timestamps: dict[str, Any] = {"submitted": utcnow()}
    log_fn(console, "High-priority submitted", high)

    logged: set[str] = set()
    while time.monotonic() < deadline:
        if "low_evicted" not in timestamps:
            evicted = kube.workload_condition(low, "Evicted")
            if evicted:
                timestamps["low_evicted"] = evicted
                log_fn(console, "Low-priority evicted", "")

        jobs.observe(high, scenario.high_priority.nodes, timestamps)
        log_phases_fn(console, timestamps, logged)

        if "completed" in timestamps or "failed" in timestamps:
            break
        time.sleep(settings.poll_interval_s)

    while time.monotonic() < deadline:
        requeued = kube.workload_condition(low, "QuotaReserved")
        if requeued and requeued > timestamps.get("low_evicted", "9999"):
            timestamps["low_requeued"] = requeued
            log_fn(console, "Low-priority requeued", "")
            break
        time.sleep(settings.poll_interval_s)

    run_metrics: dict[str, Any] = {
        "preemption_latency_s": (
            jobs.seconds_between(timestamps["submitted"], timestamps["low_evicted"])
            if "low_evicted" in timestamps
            else None
        ),
    }

    _save_logs(low, run_dir)
    _save_logs(high, run_dir)

    failures = criteria.evaluate(scenario.checks, timestamps, run_metrics, scenario)
    kube.delete_trainjob(low)
    kube.delete_trainjob(high)
    jobs.finalize(scenario, timestamps, run_metrics, failures, run_dir)

    return not failures, failures, timestamps, run_metrics


def _save_logs(job: str, run_dir: Path) -> None:
    for pod_name, log in kube.pod_logs(job).items():
        artifacts.write_log(run_dir, pod_name, log)


def _wait_for_pods(
    job: str,
    expected: int,
    deadline: float,
    console: Console,
    message: str,
    log_fn: Any,
) -> None:
    while time.monotonic() < deadline:
        if len(kube.pod_start_times(job)) == expected:
            log_fn(console, message, "")
            return
        time.sleep(settings.poll_interval_s)
