from __future__ import annotations

import re
from dataclasses import dataclass

_REFERENCE_PATTERN = re.compile(r"(?<![A-Za-z0-9_./-])#(?P<number>[1-9][0-9]*)")
_RESOLUTION_PATTERN = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(?P<number>[1-9][0-9]*)"
)


@dataclass(frozen=True, slots=True)
class ArtifactReferences:
    referenced: frozenset[int]
    resolved: frozenset[int]


def extract_artifact_references(text: str, *, supports_resolution: bool) -> ArtifactReferences:
    referenced = {int(match.group("number")) for match in _REFERENCE_PATTERN.finditer(text)}
    resolved = (
        {int(match.group("number")) for match in _RESOLUTION_PATTERN.finditer(text)}
        if supports_resolution
        else set()
    )
    return ArtifactReferences(
        referenced=frozenset(referenced - resolved),
        resolved=frozenset(resolved),
    )


def reference_excerpt(text: str, number: int, *, radius: int = 100) -> str:
    match = re.search(rf"#{number}\b", text)
    if match is None:
        return text[: radius * 2]
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end]
