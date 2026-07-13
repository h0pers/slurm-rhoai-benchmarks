"""Central configuration, grouped in one Settings class.

ClassVar attributes are static facts (where the code lives) - pydantic
excludes them from fields, so they are not configurable. Regular fields
can be overridden with BENCH_* environment variables or a .env file at
the project root (e.g. BENCH_NAMESPACE=my-ns).

Cluster manifests (manifests/ at the repo root) are deliberately absent:
they are applied by an admin with `oc apply -f manifests/`, never read by
this application.
"""

from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Static anchors derived from this file's location (not configurable).
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent  # src/
    SCENARIOS_DIR: ClassVar[Path] = BASE_DIR.parent / "scenarios"
    # Run outputs directory.
    results_dir: Path = BASE_DIR.parent / "results"

    # Kubernetes namespace all benchmark jobs run in (see manifests/00-namespace.yaml).
    namespace: str = "slurm-bench"

    # How many times each scenario repeats unless --repetitions is given.
    repetitions: int = 3

    # Seconds between status polls while watching a running job.
    poll_interval_s: int = 5

    model_config = SettingsConfigDict(env_prefix="BENCH_", env_file=BASE_DIR.parent / ".env")


settings = Settings()
