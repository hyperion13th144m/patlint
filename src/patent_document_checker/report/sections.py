from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape


def render_claim_relationships(claims: Sequence[object] | None) -> str:
    if claims is None:
        return ""

    by_number = {int(getattr(claim, "number")): claim for claim in claims}
    referenced_by: dict[int, list[int]] = {number: [] for number in by_number}
    for claim in claims:
        claim_number = int(getattr(claim, "number"))
        for referenced in getattr(claim, "referenced_claims", []):
            referenced_by.setdefault(int(referenced), []).append(claim_number)

    rows = []
    for claim in sorted(claims, key=lambda item: int(getattr(item, "number"))):
        claim_number = int(getattr(claim, "number"))
        references = [int(value) for value in getattr(claim, "referenced_claims", [])]
        incoming = sorted(set(referenced_by.get(claim_number, [])))
        if not references:
            relation_type = "独立項"
        elif len(set(references)) > 1:
            relation_type = "複数従属項"
        else:
            relation_type = "従属項"

        states = []
        if getattr(claim, "is_multi_multi", False):
            states.append("マルチマルチ")
        if getattr(claim, "references_multi_multi", False):
            states.append("マルチマルチを引用")
        if getattr(claim, "references_multiple_dependent", False):
            states.append("複数従属項を引用")

        rows.append(
            "<tr>"
            f"<td>請求項{claim_number}</td>"
            f"<td>{escape(_format_claim_numbers(references))}</td>"
            f"<td>{escape(_format_claim_numbers(incoming))}</td>"
            f"<td>{escape(relation_type)}</td>"
            f"<td>{escape('、'.join(states) if states else '－')}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="5">No claims.</td></tr>')

    return (
        '<section class="claim-relationships">'
        '<h2>請求項の関係</h2>'
        '<table>'
        '<thead><tr><th>請求項</th><th>従属先</th><th>被従属</th><th>種別</th><th>状態</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        '</section>'
    )


def _format_claim_numbers(numbers: Sequence[int]) -> str:
    if not numbers:
        return "－"
    return "、".join(f"請求項{number}" for number in numbers)


def render_unit_checks(unit_checks: Sequence[object] | None) -> str:
    if unit_checks is None:
        return ""

    rows = []
    for item in unit_checks:
        rows.append(
            "<tr>"
            f"<td>{escape(str(getattr(item, 'line', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'col', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'matched', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'number', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'unit', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'level', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'message', '')))}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="7">No unit expressions.</td></tr>')

    return (
        '<section class="unit-checks">'
        '<h2>単位チェック</h2>'
        '<table>'
        '<thead><tr><th>行</th><th>桁</th><th>マッチ</th><th>数値</th><th>単位</th><th>Level</th><th>Message</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        '</section>'
    )


def render_term_occurrences(
    term_occurrences: Mapping[str, Sequence[str]] | None,
) -> str:
    if term_occurrences is None:
        return ""

    rows = []
    for term, locations in sorted(term_occurrences.items()):
        rows.append(
            f"<tr><td>{escape(term)}</td><td>{escape('、'.join(locations))}</td></tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="2">No term occurrences.</td></tr>')

    return (
        '<section class="term-occurrences">'
        "<h2>語句出現表</h2>"
        "<table>"
        "<thead><tr><th>語句</th><th>出現場所</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</section>"
    )


def render_debug_terms(
    debug_terms_by_claim: Mapping[int, Sequence[str]] | None,
    debug_terms_with_signs: Sequence[object] | None,
) -> str:
    if debug_terms_by_claim is None and debug_terms_with_signs is None:
        return ""

    return (
        '<section class="debug">'
        "<h2>Debug</h2>"
        f"{_render_debug_claim_terms(debug_terms_by_claim)}"
        f"{_render_debug_terms_with_signs(debug_terms_with_signs)}"
        "</section>"
    )


def _render_debug_claim_terms(
    debug_terms_by_claim: Mapping[int, Sequence[str]] | None,
) -> str:
    if debug_terms_by_claim is None:
        return ""

    rows = []
    for claim_number, terms in sorted(debug_terms_by_claim.items()):
        terms_text = ", ".join(terms)
        rows.append(
            f"<tr><td>請求項{claim_number}</td><td>{escape(terms_text)}</td></tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="2">No extracted terms.</td></tr>')

    return (
        "<h3>抽出語句一覧</h3>"
        "<table>"
        "<thead><tr><th>Claim</th><th>Terms</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _render_debug_terms_with_signs(
    debug_terms_with_signs: Sequence[object] | None,
) -> str:
    if debug_terms_with_signs is None:
        return ""

    rows = []
    for item in debug_terms_with_signs:
        rows.append(
            "<tr>"
            f"<td>{escape(str(getattr(item, 'source', '') or ''))}</td>"
            f"<td>{escape(str(getattr(item, 'whole_string', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'term', '')))}</td>"
            f"<td>{escape(str(getattr(item, 'sign', '')))}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="4">No extracted terms with signs.</td></tr>')

    return (
        "<h3>符号付語句一覧</h3>"
        "<table>"
        "<thead><tr><th>Source</th><th>Whole</th><th>Term</th><th>Sign</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )
