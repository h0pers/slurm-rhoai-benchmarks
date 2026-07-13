"""Scenario execution engine - the single entry point for all benchmark flows.

Dispatches to the scenario runners in bench.scenarios and wraps results
into RunResult. The CLI and notebooks both call run() as their sole
entry point.
"""

import dataclasses
from pathlib import Path
from typing import Any

from rich.console import Console

from bench.runner import artifacts
from bench.runner.console import (
    log,
    log_phases,
    print_checks,
    print_footer,
    print_header,
    print_metrics,
)
from bench.schemas import GangScenario, PreemptionScenario, TrainScenario

Scenario = TrainScenario | GangScenario | PreemptionScenario


@dataclasses.dataclass
class RunResult:
    passed: bool
    failures: list[str]
    run_dir: Path
    timestamps: dict[str, Any]
    metrics: dict[str, Any]


def run(scenario: Scenario, console: Console) -> RunResult:
    """Execute one benchmark run and return the result."""
    from bench.scenarios import run_gang, run_preemption, run_train

    print_header(scenario, console)
    run_dir = artifacts.new_run_dir(scenario.name)

    if isinstance(scenario, TrainScenario):
        passed, failures, timestamps, metrics = run_train(
            scenario, run_dir, console, log, log_phases
        )
    elif isinstance(scenario, GangScenario):
        passed, failures, timestamps, metrics = run_gang(
            scenario, run_dir, console, log, log_phases
        )
    elif isinstance(scenario, PreemptionScenario):
        passed, failures, timestamps, metrics = run_preemption(
            scenario, run_dir, console, log, log_phases
        )
    else:
        raise ValueError(f"Unknown scenario type: {type(scenario).__name__}")

    result = RunResult(
        passed=passed,
        failures=failures,
        run_dir=run_dir,
        timestamps=timestamps,
        metrics=metrics,
    )

    print_metrics(result.metrics, console)
    print_checks(scenario.checks, result.timestamps, result.metrics, scenario, console)
    print_footer(result.passed, result.failures, result.run_dir, console)
    return result
