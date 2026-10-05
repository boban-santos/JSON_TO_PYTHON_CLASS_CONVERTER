"""Multi-sample merger: merges multiple JSON objects and tracks field presence across samples."""

from __future__ import annotations

from typing import Any


class MergedObject:
    """Represents a merged view of multiple dictionary samples."""

    def __init__(self, sample_count: int = 1):
        self.sample_count = sample_count
        # key -> list of observed values across samples
        self.field_values: dict[str, list[Any]] = {}
        # key -> count of samples where key was present
        self.field_presence: dict[str, int] = {}

    def is_optional(self, key: str) -> bool:
        """True if the key was missing in at least one sample or explicitly None in some sample."""
        presence = self.field_presence.get(key, 0)
        if presence < self.sample_count:
            return True
        values = self.field_values.get(key, [])
        return any(v is None for v in values)


def merge_samples(samples: list[dict[str, Any]]) -> MergedObject:
    """Merge a list of JSON dict samples into a MergedObject."""
    if not samples:
        return MergedObject(sample_count=0)

    merged = MergedObject(sample_count=len(samples))
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        for k, v in sample.items():
            merged.field_presence[k] = merged.field_presence.get(k, 0) + 1
            if k not in merged.field_values:
                merged.field_values[k] = []
            merged.field_values[k].append(v)

    return merged
