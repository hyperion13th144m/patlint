from __future__ import annotations

import re
from collections.abc import Iterable

from .common import dedupe_preserving_order, is_noise_term, prepare_term
from .dictionaries import load_dictionary_stems
from .models import ClaimTermOccurrence
from .normalization import normalize_term_text
from .patterns import (
    Candidate,
    DICTIONARY_SUFFIXES,
    REFERENCE_TERM_PREFIXES,
    TERM_PATTERNS,
    TERM_PREFIXES,
)

_DEFAULT_DICTIONARY_TERMS = object()
DictionaryTerms = Iterable[str] | None | object


def extract_claim_terms(
    text: str, dictionary_terms: DictionaryTerms = _DEFAULT_DICTIONARY_TERMS
) -> list[str]:
    normalized = normalize_term_text(text)
    return dedupe_preserving_order(
        candidate[3]
        for candidate in _term_candidates(normalized, dictionary_terms=dictionary_terms)
    )


def extract_claim_term_occurrences(
    text: str, dictionary_terms: DictionaryTerms = _DEFAULT_DICTIONARY_TERMS
) -> list[ClaimTermOccurrence]:
    normalized = normalize_term_text(text)
    occurrences: list[ClaimTermOccurrence] = []
    for start, end, _, term in _term_candidates(
        normalized, dictionary_terms=dictionary_terms
    ):
        raw_term = normalized[start:end]
        occurrences.append(
            ClaimTermOccurrence(
                term=term,
                has_reference_prefix=_has_reference_term_prefix(raw_term),
                start=start,
                end=end,
            )
        )
    return occurrences


def extract_claim_terms_by_number(
    claims: Iterable[object],
    dictionary_terms: DictionaryTerms = _DEFAULT_DICTIONARY_TERMS,
) -> dict[int, list[str]]:
    terms_by_number: dict[int, list[str]] = {}
    for claim in claims:
        number = getattr(claim, "number")
        text = getattr(claim, "text")
        terms_by_number[number] = extract_claim_terms(text, dictionary_terms)
    return terms_by_number


def _term_candidates(
    normalized_text: str,
    dictionary_terms: DictionaryTerms = _DEFAULT_DICTIONARY_TERMS,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    resolved_dictionary_terms = _resolve_dictionary_terms(dictionary_terms)

    for priority, pattern in enumerate(TERM_PATTERNS, start=1):
        for match in pattern.finditer(normalized_text):
            term = prepare_term(match.group(0))
            if is_noise_term(term):
                continue
            candidates.append((match.start(), match.end(), priority, term))

    if resolved_dictionary_terms is not None:
        for raw_stem in resolved_dictionary_terms:
            stem = prepare_term(raw_stem)
            if is_noise_term(stem):
                continue
            pattern = _dictionary_stem_pattern(stem)
            for match in pattern.finditer(normalized_text):
                term = prepare_term(match.group(0))
                if is_noise_term(term):
                    continue
                candidates.append((match.start(), match.end(), 0, term))

    return _select_non_overlapping(candidates)


def _resolve_dictionary_terms(dictionary_terms: DictionaryTerms) -> Iterable[str] | None:
    if dictionary_terms is _DEFAULT_DICTIONARY_TERMS:
        return load_dictionary_stems()
    if dictionary_terms is None:
        return None
    return dictionary_terms  # type: ignore[return-value]


def _dictionary_stem_pattern(stem: str) -> re.Pattern[str]:
    prefix_pattern = "|".join(re.escape(prefix) for prefix in TERM_PREFIXES)
    suffix_pattern = "|".join(re.escape(suffix) for suffix in DICTIONARY_SUFFIXES)
    return re.compile(rf"(?:{prefix_pattern})?{re.escape(stem)}(?:{suffix_pattern})")


def _has_reference_term_prefix(value: str) -> bool:
    return any(value.startswith(prefix) for prefix in REFERENCE_TERM_PREFIXES)


def _select_non_overlapping(candidates: list[Candidate]) -> list[Candidate]:
    selected: list[Candidate] = []
    occupied: list[tuple[int, int]] = []
    for candidate in sorted(
        candidates, key=lambda item: (item[0], -(item[1] - item[0]), item[2])
    ):
        start, end, _, _ = candidate
        if any(
            start < occupied_end and end > occupied_start
            for occupied_start, occupied_end in occupied
        ):
            continue
        selected.append(candidate)
        occupied.append((start, end))
    return sorted(selected, key=lambda item: item[0])
