from __future__ import annotations

import re

from patent_checker_common import Diagnostic

from ..parser import Claim
from ..terms import extract_claim_term_occurrences, normalize_term_text
from .common import _claim_location


def check_missing_claim_term_reference_prefix(claims: list[Claim]) -> list[Diagnostic]:
    by_number = {claim.number: claim for claim in claims}
    terms_by_claim = {
        claim.number: extract_claim_term_occurrences(claim.text) for claim in claims
    }
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        seen_terms = set(_referenced_claim_terms(claim, by_number, terms_by_claim))
        reported_terms: set[str] = set()

        for occurrence in terms_by_claim[claim.number]:
            if (
                occurrence.term in seen_terms
                and not occurrence.has_reference_prefix
                and not _is_claim_category_term_occurrence(claim.text, occurrence.start)
                and occurrence.term not in reported_terms
            ):
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_TERM_REFERENCE_PREFIX",
                        severity="warning",
                        message=(
                            f"請求項{claim.number}の語句 {occurrence.term} は、"
                            "2回目以降または引用元の請求項で出現済みですが、"
                            "前記・該・当該が付いていません（前記ぬけ）。"
                        ),
                        location=_claim_location(claim),
                        suggestion="2回目以降の語句には前記・該・当該を付けるか、語句の使い方を確認してください。",
                    )
                )
                reported_terms.add(occurrence.term)

            seen_terms.add(occurrence.term)

    return diagnostics


def _is_claim_category_term_occurrence(claim_text: str, occurrence_start: int) -> bool:
    normalized = normalize_term_text(claim_text)
    before = normalized[:occurrence_start]
    phrase = before.rsplit("。", maxsplit=1)[-1]
    return re.search(r"請求項.{0,40}に記載(?:の|する|された)$", phrase) is not None


def _referenced_claim_terms(
    claim: Claim,
    by_number: dict[int, Claim],
    terms_by_claim: dict[int, list[object]],
) -> set[str]:
    terms: set[str] = set()
    for referenced in claim.referenced_claims:
        if referenced not in by_number:
            continue
        terms.update(occurrence.term for occurrence in terms_by_claim.get(referenced, []))
    return terms
