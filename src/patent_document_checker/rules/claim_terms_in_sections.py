from __future__ import annotations

from patent_checker_common import Diagnostic

from ..parser import Claim
from ..terms import extract_claim_terms, normalize_term_text
from .common import _claim_location, _section_paragraph_text


def check_claim_terms_in_embodiments(
    claims: list[Claim], tree: object | None
) -> list[Diagnostic]:
    return _check_claim_terms_in_section(
        claims=claims,
        tree=tree,
        section_kind="description_of_embodiments",
        rule_id="CLAIM_TERM_IN_EMBODIMENTS",
        section_label="実施形態",
    )


def check_claim_terms_in_tech_solution(
    claims: list[Claim], tree: object | None
) -> list[Diagnostic]:
    return _check_claim_terms_in_section(
        claims=claims,
        tree=tree,
        section_kind="tech_solution",
        rule_id="CLAIM_TERM_IN_TECH_SOLUTION",
        section_label="解決手段",
    )


def _check_claim_terms_in_section(
    claims: list[Claim],
    tree: object | None,
    section_kind: str,
    rule_id: str,
    section_label: str,
) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    section_text = _section_paragraph_text(tree, section_kind)
    if not section_text:
        return []

    normalized_section_text = normalize_term_text(section_text)
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        for term in extract_claim_terms(claim.text):
            if normalize_term_text(term) in normalized_section_text:
                continue
            diagnostics.append(
                Diagnostic(
                    rule_id=rule_id,
                    severity="warning",
                    message=f"請求項の語句 {term}は、{section_label}に記載されていません",
                    location=_claim_location(claim),
                    suggestion=f"請求項の語句が{section_label}に記載されているか確認してください。",
                )
            )

    return diagnostics
