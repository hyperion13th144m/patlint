from __future__ import annotations

import re

from patent_checker_common import Diagnostic, DiagnosticLocation

from ..parser import Claim
from .common import _claim_location, _dedupe_strings_preserving_order, _node_text


def check_invention_title_matches_independent_claims(
    claims: list[Claim], tree: object | None
) -> list[Diagnostic]:
    title_terms = _invention_title_terms(tree)
    if not title_terms:
        return []

    claim_terms = _independent_claim_terminal_terms(claims)
    if title_terms == claim_terms:
        return []

    return [
        Diagnostic(
            rule_id="INVENTION_TITLE_CLAIM_MISMATCH",
            severity="error",
            message=(
                "発明の名称と独立請求項の末尾語句が一致していません"
                f"（発明の名称: {', '.join(title_terms)} / "
                f"独立請求項: {', '.join(claim_terms) if claim_terms else 'なし'}）。"
            ),
            location=DiagnosticLocation(
                source_type="document", section_type="invention_title"
            ),
            suggestion="発明の名称と独立請求項に記載された発明カテゴリが一致しているか確認してください。",
        )
    ]


def _invention_title_terms(tree: object | None) -> list[str]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    terms: list[str] = []
    for title in tree.find_all(kind="invention_title"):
        for term in re.split(r"、|，|及び|並びに|および|ならびに", _node_text(title)):
            stripped = term.strip()
            if stripped:
                terms.append(stripped)

    return _dedupe_strings_preserving_order(terms)


def _independent_claim_terminal_terms(claims: list[Claim]) -> list[str]:
    terms = []
    for claim in claims:
        if claim.referenced_claims:
            continue
        term = _claim_terminal_term(claim.text)
        if term:
            terms.append(term)
    return _dedupe_strings_preserving_order(terms)


def _claim_terminal_term(text: str) -> str:
    normalized = re.sub(r"\s+", "", text).strip("。．")
    if not normalized:
        return ""

    marker = "ことを特徴とする"
    if marker in normalized:
        normalized = normalized.rsplit(marker, maxsplit=1)[-1]

    normalized = re.sub(
        r"^請求項[0-9０-９]+(?:(?:又は|または|及び|および|から|乃至|ないし|～|－|-|、|，|,)(?:請求項)?[0-9０-９]+)*に記載の",
        "",
        normalized,
    )
    return normalized.strip("、，。．")


def check_dependent_claim_invention_name_matches_references(
    claims: list[Claim],
) -> list[Diagnostic]:
    by_number = {claim.number: claim for claim in claims}
    terminal_terms = {
        claim.number: _claim_terminal_term(claim.text) for claim in claims
    }
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        if not claim.referenced_claims:
            continue

        claim_term = terminal_terms.get(claim.number, "")
        if not claim_term:
            continue

        mismatches = []
        for referenced in claim.referenced_claims:
            referenced_claim = by_number.get(referenced)
            if referenced_claim is None:
                continue
            referenced_term = terminal_terms.get(referenced, "")
            if referenced_term and referenced_term != claim_term:
                mismatches.append(f"請求項{referenced}: {referenced_term}")

        if not mismatches:
            continue

        diagnostics.append(
            Diagnostic(
                rule_id="DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH",
                severity="error",
                message=(
                    f"請求項{claim.number}の発明の名称 {claim_term} は、"
                    "参照元請求項の発明の名称と一致していません"
                    f"（参照元: {', '.join(mismatches)}）。"
                ),
                location=_claim_location(claim),
                suggestion="従属請求項の末尾語句と参照元請求項の末尾語句が一致しているか確認してください。",
            )
        )

    return diagnostics
