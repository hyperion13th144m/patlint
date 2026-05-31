from __future__ import annotations

from collections.abc import Iterable

from .claim_terms import extract_claim_terms
from .signed_terms import extract_document_terms_with_signs


def extract_term_occurrences(claims: Iterable[object], tree: object | None) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = {}

    for claim in claims:
        location = f"請求項{getattr(claim, 'number')}"
        for term in extract_claim_terms(getattr(claim, "text")):
            _add_occurrence(occurrences, term, location)

    for item in extract_document_terms_with_signs(tree):
        _add_occurrence(occurrences, item.whole_string, item.source or "不明")

    return dict(sorted(occurrences.items()))


def _add_occurrence(occurrences: dict[str, list[str]], term: str, location: str) -> None:
    locations = occurrences.setdefault(term, [])
    if location not in locations:
        locations.append(location)
