from __future__ import annotations

import re
from collections.abc import Iterable

from .normalization import normalize_term_text
from .patterns import STOPWORDS, TERM_PREFIXES


def prepare_term(value: str) -> str:
    term = normalize_term_text(value).strip("、。，．・:：;；()（）[]［］{}｛｝")
    changed = True
    while changed:
        changed = False
        for prefix in TERM_PREFIXES:
            if term.startswith(prefix) and len(term) > len(prefix) + 1:
                term = term[len(prefix) :]
                changed = True
                break
    return term


def is_noise_term(term: str) -> bool:
    if len(term) < 2:
        return True
    if term in STOPWORDS:
        return True
    if term.startswith("請求項"):
        return True
    if re.fullmatch(r"[0-9０-９]+", term):
        return True
    return False


def node_text(node: object) -> str:
    chunks = [getattr(node, "text", "")]
    for child in getattr(node, "children", []):
        chunks.append(node_text(child))
    return "\n".join(chunk for chunk in chunks if chunk)


def paragraph_source(paragraph: object) -> str:
    number = getattr(paragraph, "number", None)
    if isinstance(number, int):
        return f"{number:04d}"
    tag_name = getattr(paragraph, "tag_name", None)
    return str(tag_name) if tag_name else ""


def dedupe_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
