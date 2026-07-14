"""Train scenario flow (workload classes 1-4)."""

import time
from pathlib import Path
from typing import Any

from rich.console import Console

from bench.config import settings
from bench.runner import criteria, jobs, kube
from bench.schemas import TrainScenario
from bench.utils import utcnow


def run_train(
    scenario: TrainScenario,
    run_dir: Path,
    console: Console,
    log_fn: Any,
    log_phases_fn: Any,
) -> tuple[bool, list[str], dict[str, Any], dict[str, Any]]:
    job = jobs.submit_train(scenario)
    timestamps: dict[str, Any] = {"submitted": utcnow()}
    log_fn(console, "Submitted", job)

    deadline = time.monotonic() + scenario.timeout_s
    logged: set[str] = set()

    while time.monotonic() < deadline:
        jobs.observe(job, scenario.nodes, timestamps)
        log_phases_fn(console, timestamps, logged)

        if scenario.fault and "pods_running" in timestamps and "fault_injected" not in timestamps:
            _inject_fault(scenario, job, timestamps, console, log_fn)
            _watch_recovery(scenario, job, timestamps, deadline, console, log_fn)

        if "completed" in timestamps or "failed" in timestamps:
            log_phases_fn(console, timestamps, logged)
            break

        time.sleep(settings.poll_interval_s)

    run_metrics = jobs.collect(scenario, job, timestamps, run_dir)
    if "recovery_s" in timestamps:
        run_metrics["recovery_s"] = timestamps.pop("recovery_s")

    failures = criteria.evaluate(scenario.checks, timestamps, run_metrics, scenario)
    kube.delete_trainjob(job)
    jobs.finalize(scenario, timestamps, run_metrics, failures, run_dir)

    return not failures, failures, timestamps, run_metrics


def _inject_fault(
    scenario: TrainScenario,
    job: str,
    timestamps: dict,
    console: Console,
    log_fn: Any,
) -> None:
    console.print(f"  waiting {scenario.fault.after_s}s before fault injection...")
    time.sleep(scenario.fault.after_s)

    worker_index = int(scenario.fault.target.rsplit("-", 1)[-1])
    timestamps["fault_injected"] = kube.delete_worker_pod(job, worker_index)
    log_fn(console, "Fault injected", f"killed worker {scenario.fault.target}")


def _watch_recovery(
    scenario: TrainScenario,
    job: str,
    timestamps: dict,
    deadline: float,
    console: Console,
    log_fn: Any,
) -> None:
    while time.monotonic() < deadline:
        started = kube.pod_start_times(job)

        if (
            kube.newest_pod_created_after(job, timestamps["fault_injected"])
            and len(started) == scenario.nodes
        ):
            timestamps["resumed"] = max(started)
            recovery_s = jobs.seconds_between(timestamps["fault_injected"], timestamps["resumed"])
            timestamps["recovery_s"] = recovery_s
            log_fn(console, "Recovered", f"recovery: {recovery_s}s")
            break

        # Stop watching if the job reached a terminal state without recovering
        # (e.g. it exhausted its restart budget). Otherwise this loop would
        # spin until the full timeout_s and the run would never record a result.
        if kube.job_condition(job, "Failed") or kube.job_condition(job, "Complete"):
            log_fn(console, "No recovery", "job reached terminal state before recovery")
            break

        time.sleep(settings.poll_interval_s)

    timestamps.pop("pods_running", None)
    timestamps.pop("gang_start_spread_s", None)
