from __future__ import annotations

from pathlib import Path


def find_data_dir(name: str, anchor: Path | None = None) -> Path | None:
    """Find a project data directory from cwd or a module anchor path."""
    for parent in _search_roots(anchor):
        candidate = parent / name
        if candidate.is_dir():
            return candidate
    return None


def _search_roots(anchor: Path | None = None) -> tuple[Path, ...]:
    cwd = Path.cwd()
    roots: list[Path] = [cwd, *cwd.parents]
    if anchor is not None:
        resolved = anchor.resolve()
        anchor_dir = resolved if resolved.is_dir() else resolved.parent
        roots.extend([anchor_dir, *anchor_dir.parents])
    return tuple(_dedupe_paths(roots))


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        result.append(path)
        seen.add(path)
    return result
