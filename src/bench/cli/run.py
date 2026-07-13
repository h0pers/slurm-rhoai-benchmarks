"""bench run - execute a benchmark scenario."""

import json
from typing import Annotated

import typer

from bench import runner
from bench.schemas import load


def run(
    scenario_name: str = typer.Argument(help="Scenario name (e.g. single-gpu, gang-scheduling)."),
    repetitions: Annotated[
        int | None, typer.Option("-r", "--repetitions", help="Override repetition count.")
    ] = None,
    timeout: Annotated[int | None, typer.Option("--timeout", help="Override timeout_s.")] = None,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate config and print plan without submitting."
    ),
) -> None:
    """Run a benchmark scenario."""
    from bench.cli import console

    scenario = load(scenario_name)

    if timeout is not None:
        scenario.timeout_s = timeout

    reps = repetitions or scenario.repetitions

    if dry_run:
        console.print(f"scenario: {scenario.name} ({scenario.kind})")
        console.print(f"description: {scenario.description}")
        console.print(f"repetitions: {reps}")
        console.print(f"timeout_s: {scenario.timeout_s}")
        console.print(f"checks: {scenario.checks}")
        console.print(f"config: {json.dumps(scenario.model_dump(), indent=2, default=str)}")
        return

    passed = 0
    for i in range(reps):
        if reps > 1:
            console.print(f"\n[Run {i + 1}/{reps}]")

        result = runner.run(scenario, console)

        if result.passed:
            passed += 1

    if reps > 1:
        console.print(f"\nSummary: {passed}/{reps} passed")

    raise typer.Exit(code=0 if passed == reps else 1)
