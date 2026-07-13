"""Small generic helpers shared across modules."""

from datetime import UTC, datetime


def utcnow() -> str:
    """Current time as ISO-8601 UTC - the single timestamp format used everywhere."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def durations(timestamps: dict[str, str], phases: dict[str, tuple[str, str]]) -> dict[str, float]:
    """Seconds between timestamp pairs, for phases where both boundaries exist.

    Args:
        timestamps: name -> ISO-8601 UTC string.
        phases: phase name -> (start timestamp name, end timestamp name).
    """

    def parse(key: str) -> datetime | None:
        value = timestamps.get(key)
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None

    result = {}
    for phase, (start_key, end_key) in phases.items():
        start, end = parse(start_key), parse(end_key)
        if start and end:
            result[phase] = round((end - start).total_seconds(), 1)
    return result
