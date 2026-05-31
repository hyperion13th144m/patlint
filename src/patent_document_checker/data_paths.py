from __future__ import annotations

from pathlib import Path
import sys


def find_data_dir(name: str, anchor: Path | None = None) -> Path | None:
    """Find the first project data directory from cwd, exe dir, or module anchor."""
    data_dirs = find_data_dirs(name, anchor=anchor)
    return data_dirs[0] if data_dirs else None


def find_data_dirs(name: str, anchor: Path | None = None) -> tuple[Path, ...]:
    """Find matching data directories from cwd, frozen exe dir, and module anchor."""
    result: list[Path] = []
    for parent in _search_roots(anchor):
        candidate = parent / name
        if candidate.is_dir():
            result.append(candidate)
    return tuple(_dedupe_paths(result))


def _search_roots(anchor: Path | None = None) -> tuple[Path, ...]:
    cwd = Path.cwd()
    roots: list[Path] = [cwd, *cwd.parents]
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        roots.extend([executable_dir, *executable_dir.parents])
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
