from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..data_paths import find_data_dir


DEFAULT_TERMS_FILENAME = "default-terms.txt"
CUSTOM_TERMS_FILENAME = "custom-terms.txt"


@lru_cache(maxsize=1)
def load_dictionary_stems() -> tuple[str, ...]:
    words_dir = find_data_dir("words", anchor=Path(__file__))
    if words_dir is None:
        return ()

    stems: list[str] = []
    for filename in (DEFAULT_TERMS_FILENAME, CUSTOM_TERMS_FILENAME):
        stems.extend(_load_terms_file(words_dir / filename))
    return tuple(_dedupe_preserving_order(stems))


def _load_terms_file(path: Path) -> list[str]:
    if not path.exists():
        return []

    terms: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(line)
    return terms


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result
