from __future__ import annotations

from patent_checker_common import Diagnostic, DiagnosticLocation

from ..terms import extract_document_terms_with_signs


def check_term_sign_conflicts(tree: object | None) -> list[Diagnostic]:
    terms_with_signs = extract_document_terms_with_signs(tree)
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_check_same_term_different_signs(terms_with_signs))
    diagnostics.extend(_check_same_sign_different_terms(terms_with_signs))
    return diagnostics


def _check_same_term_different_signs(terms_with_signs: list[object]) -> list[Diagnostic]:
    by_term: dict[str, dict[str, set[str]]] = {}

    for item in terms_with_signs:
        sources_by_sign = by_term.setdefault(item.term, {})
        sources = sources_by_sign.setdefault(item.sign, set())
        sources.add(item.source or "不明")

    diagnostics: list[Diagnostic] = []
    for term, sources_by_sign in sorted(by_term.items()):
        if len(sources_by_sign) < 2:
            continue

        sign_locations = _format_grouped_locations(sources_by_sign)
        diagnostics.append(
            Diagnostic(
                rule_id="TERM_SIGN_CONFLICT",
                severity="warning",
                message=(
                    f"符号付語句 {term} は、複数の符号で記載されています"
                    f"（{sign_locations}）。"
                ),
                location=DiagnosticLocation(
                    source_type="document", section_type="terms_with_signs"
                ),
                suggestion="同じ語句に対応する符号が統一されているか確認してください。",
            )
        )

    return diagnostics


def _check_same_sign_different_terms(terms_with_signs: list[object]) -> list[Diagnostic]:
    by_sign: dict[str, dict[str, set[str]]] = {}

    for item in terms_with_signs:
        sources_by_term = by_sign.setdefault(item.sign, {})
        sources = sources_by_term.setdefault(item.term, set())
        sources.add(item.source or "不明")

    diagnostics: list[Diagnostic] = []
    for sign, sources_by_term in sorted(by_sign.items()):
        if len(sources_by_term) < 2:
            continue

        term_locations = _format_grouped_locations(sources_by_term)
        diagnostics.append(
            Diagnostic(
                rule_id="SIGN_TERM_CONFLICT",
                severity="warning",
                message=(
                    f"符号 {sign} は、複数の語句で記載されています"
                    f"（{term_locations}）。"
                ),
                location=DiagnosticLocation(
                    source_type="document", section_type="terms_with_signs"
                ),
                suggestion="同じ符号に対応する語句が統一されているか確認してください。",
            )
        )

    return diagnostics


def _format_grouped_locations(grouped_locations: dict[str, set[str]]) -> str:
    return "、".join(
        f"{label}: {', '.join(sorted(sources))}"
        for label, sources in sorted(grouped_locations.items())
    )
