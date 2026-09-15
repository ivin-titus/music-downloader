from __future__ import annotations

from pathlib import Path


def remove_stale_partials(root: Path) -> list[Path]:
    """Remove incomplete download artifacts from a failed/interrupted run."""
    removed: list[Path] = []
    if not root.exists():
        return removed

    for path in root.rglob("*.part"):
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed
