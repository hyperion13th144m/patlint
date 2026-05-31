from __future__ import annotations

from patent_checker_common import Diagnostic, DiagnosticLocation

from ..parser import Claim
from ..terms import extract_claim_terms, extract_document_terms_with_signs


def check_term_variations(claims: list[Claim], tree: object | None) -> list[Diagnostic]:
    term_sources = _document_term_sources(claims, tree)
    terms = sorted(term_sources)
    diagnostics: list[Diagnostic] = []

    for index, first in enumerate(terms):
        for second in terms[index + 1 :]:
            suffix = _common_suffix(first, second)
            if (
                len(suffix) >= 2
                and first[0] != second[0]
                and _unmatched_prefix_lengths(first, second, suffix) == (1, 1)
            ):
                diagnostics.append(
                    Diagnostic(
                        rule_id="TERM_VARIATION",
                        severity="warning",
                        message=(
                            f"語句 {first} と {second} は、末尾「{suffix}」が一致していますが"
                            "先頭が異なります。"
                        ),
                        location=DiagnosticLocation(
                            source_type="document", section_type="terms"
                        ),
                        suggestion="語句の表記揺れではないか確認してください。",
                    )
                )

            prefix = _common_prefix(first, second)
            if (
                len(prefix) >= 2
                and first[-1] != second[-1]
                and _unmatched_suffix_lengths(first, second, prefix) == (1, 1)
            ):
                diagnostics.append(
                    Diagnostic(
                        rule_id="TERM_VARIATION",
                        severity="warning",
                        message=(
                            f"語句 {first} と {second} は、先頭「{prefix}」が一致していますが"
                            "末尾が異なります。"
                        ),
                        location=DiagnosticLocation(
                            source_type="document", section_type="terms"
                        ),
                        suggestion="語句の表記揺れではないか確認してください。",
                    )
                )

    return diagnostics


def _document_term_sources(claims: list[Claim], tree: object | None) -> dict[str, str]:
    term_sources: dict[str, str] = {}
    for claim in claims:
        for term in extract_claim_terms(claim.text):
            if len(term) >= 3:
                term_sources.setdefault(term, f"請求項{claim.number}")
    for item in extract_document_terms_with_signs(tree):
        if len(item.term) >= 3:
            term_sources.setdefault(item.term, item.source or "不明")
    return term_sources


def _unmatched_prefix_lengths(first: str, second: str, suffix: str) -> tuple[int, int]:
    return len(first) - len(suffix), len(second) - len(suffix)


def _unmatched_suffix_lengths(first: str, second: str, prefix: str) -> tuple[int, int]:
    return len(first) - len(prefix), len(second) - len(prefix)


def _common_prefix(first: str, second: str) -> str:
    index = 0
    max_length = min(len(first), len(second))
    while index < max_length and first[index] == second[index]:
        index += 1
    return first[:index]


def _common_suffix(first: str, second: str) -> str:
    index = 0
    max_length = min(len(first), len(second))
    while index < max_length and first[-index - 1] == second[-index - 1]:
        index += 1
    return first[len(first) - index :] if index else ""
