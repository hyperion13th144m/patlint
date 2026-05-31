from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path

from patent_checker_common import DiagnosticsResult

from ..diagnostic_view import diagnostics_to_views

from .reference_signs import render_reference_sign_list
from .sections import (
    render_claim_relationships,
    render_debug_terms,
    render_term_occurrences,
    render_unit_checks,
)

_TEMPLATE_PATH = Path(__file__).with_name("templates") / "report.html"


def render_html_report(
    result: DiagnosticsResult,
    term_occurrences: Mapping[str, Sequence[str]] | None = None,
    terms_with_signs: Sequence[object] | None = None,
    claims: Sequence[object] | None = None,
    unit_checks: Sequence[object] | None = None,
    debug_terms_by_claim: Mapping[int, Sequence[str]] | None = None,
    debug_terms_with_signs: Sequence[object] | None = None,
) -> str:
    summary = result.summary
    values = {
        "SOURCE": escape(result.source or ""),
        "ERROR_COUNT": str(summary["error"]),
        "WARNING_COUNT": str(summary["warning"]),
        "INFO_COUNT": str(summary["info"]),
        "DIAGNOSTIC_ROWS": _render_diagnostic_rows(result),
        "TERM_OCCURRENCES_SECTION": render_term_occurrences(term_occurrences),
        "CLAIM_RELATIONSHIPS_SECTION": render_claim_relationships(claims),
        "UNIT_CHECKS_SECTION": render_unit_checks(unit_checks),
        "REFERENCE_SIGN_LIST_SECTION": render_reference_sign_list(terms_with_signs),
        "DEBUG_TERMS_SECTION": render_debug_terms(
            debug_terms_by_claim, debug_terms_with_signs
        ),
    }
    return _render_template(_load_template(), values)


def _load_template() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _render_template(template: str, values: Mapping[str, str]) -> str:
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace(f"{{{{{name}}}}}", value)
    return rendered


def _render_diagnostic_rows(result: DiagnosticsResult) -> str:
    rows = []
    for diagnostic in diagnostics_to_views(result.diagnostics):
        rows.append(
            f'<tr class="severity-{escape(diagnostic["severity"])}">'
            f'<td><span class="severity-badge">{escape(diagnostic["severity_label"])}</span></td>'
            f'<td>{escape(diagnostic["rule_label"])}</td>'
            f'<td><div>{escape(diagnostic["message"])}</div>'
            f'<div class="diagnostic-meta">{escape(diagnostic["rule_id"])} / {escape(diagnostic["location"])}</div></td>'
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="3">No diagnostics.</td></tr>'
