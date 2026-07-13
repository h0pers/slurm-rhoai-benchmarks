"""Scenario schema (pydantic models) and loading.

Each YAML in the scenarios directory parses into one of three models,
discriminated by its `kind` field:

    train      - a real training job (workload classes 1-4)
    gang       - blocker + measured job pair probing all-or-nothing admission
    preemption - low/high priority pair probing priority-based eviction

extra="forbid" makes any unknown or misspelled YAML key a validation error.
"""

from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from bench.config import settings


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainingConfig(StrictModel):
    model: str
    dataset: str
    dataset_size: int
    batch_size: int
    max_steps: int


class CheckpointConfig(StrictModel):
    pvc: str
    mount_path: str
    save_steps: int


class FaultConfig(StrictModel):
    action: Literal["delete-worker-pod"]
    target: str
    after_s: int


class JobShape(StrictModel):
    """Node/resource shape of one submitted job in gang/preemption scenarios."""

    nodes: int = 1
    resources_per_node: dict[str, str | int]
    hold_s: int | None = None
    priority_class: str | None = None
    submit_after_s: int | None = None


class ScenarioBase(StrictModel):
    name: str
    workload_class: int
    description: str
    queue: str
    runtime: str
    repetitions: int = settings.repetitions
    timeout_s: int
    pass_criteria: list[str]
    checks: list[str]


class TrainScenario(ScenarioBase):
    kind: Literal["train"]
    nodes: int
    resources_per_node: dict[str, str | int]
    training: TrainingConfig
    checkpoint: CheckpointConfig | None = None
    fault: FaultConfig | None = None
    baseline_scenario: str | None = None


class GangScenario(ScenarioBase):
    kind: Literal["gang"]
    blocker: JobShape
    measured: JobShape


class PreemptionScenario(ScenarioBase):
    kind: Literal["preemption"]
    low_priority: JobShape
    high_priority: JobShape


Scenario = Annotated[
    TrainScenario | GangScenario | PreemptionScenario,
    Field(discriminator="kind"),
]

_adapter = TypeAdapter(Scenario)


def load(name: str) -> TrainScenario | GangScenario | PreemptionScenario:
    """Load one scenario by its `name` field (files are named like 1-single-gpu.yaml)."""
    for path in sorted(settings.SCENARIOS_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        if raw.get("name") == name:
            return _adapter.validate_python(raw)
    names = ", ".join(s.name for s in load_all())
    raise FileNotFoundError(f"scenario '{name}' not found; available: {names}")


def load_all() -> list[TrainScenario | GangScenario | PreemptionScenario]:
    """Load every scenario, sorted by file name (numeric prefix gives the order)."""
    return [
        _adapter.validate_python(yaml.safe_load(p.read_text()))
        for p in sorted(settings.SCENARIOS_DIR.glob("*.yaml"))
    ]
