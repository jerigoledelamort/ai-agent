from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class VersionInfo:
    current_dir: Path
    previous_dir: Path | None
    version_number: int


def detect_version(current_dir: Path) -> VersionInfo:
    match = re.fullmatch(r"v(\d+)", current_dir.name)
    if not match:
        raise ValueError(
            f"Agent must be started from version directory vN; got {current_dir.name}"
        )

    number = int(match.group(1))
    previous_dir = current_dir.parent / f"v{number - 1}" if number > 1 else None
    if previous_dir and not previous_dir.exists():
        previous_dir = None

    return VersionInfo(
        current_dir=current_dir.resolve(),
        previous_dir=previous_dir.resolve() if previous_dir else None,
        version_number=number,
    )
