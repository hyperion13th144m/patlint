from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape

from patent_checker_common import DiagnosticsResult


def render_html_report(
    result: DiagnosticsResult,
    debug_terms_by_claim: Mapping[int, Sequence[str]] | None = None,
    debug_terms_with_signs: Sequence[object] | None = None,
) -> str:
    rows = []
    for diagnostic in result.diagnostics:
        location = diagnostic.location.to_dict() if diagnostic.location else {}
        rows.append(
            "<tr>"
            f"<td>{escape(diagnostic.severity)}</td>"
            f"<td>{escape(diagnostic.rule_id)}</td>"
            f"<td>{escape(diagnostic.message)}</td>"
            f"<td>{escape(str(location))}</td>"
            f"<td>{escape(diagnostic.suggestion or '')}</td>"
            "</tr>"
        )

    summary = result.summary
    debug_terms_html = _render_debug_terms(
        debug_terms_by_claim, debug_terms_with_signs
    )
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>Patent Document Checker Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; line-height: 1.6; margin: 32px; color: #1f2937; background: #ffffff; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; }}
    th {{ background: #f3f4f6; text-align: left; }}
    .summary {{ margin: 16px 0 24px; }}
  </style>
</head>
<body>
  <h1>Patent Document Checker Report</h1>
  <p>Source: {escape(result.source or "")}</p>
  <div class="summary">
    Errors: {summary["error"]} /
    Warnings: {summary["warning"]} /
    Info: {summary["info"]}
  </div>
  <table>
    <thead>
      <tr><th>Severity</th><th>Rule</th><th>Message</th><th>Location</th><th>Suggestion</th></tr>
    </thead>
    <tbody>
      {"".join(rows) or '<tr><td colspan="5">No diagnostics.</td></tr>'}
    </tbody>
  </table>
  {debug_terms_html}
</body>
</html>
"""


def _render_debug_terms(
    debug_terms_by_claim: Mapping[int, Sequence[str]] | None,
    debug_terms_with_signs: Sequence[object] | None,
) -> str:
    if debug_terms_by_claim is None and debug_terms_with_signs is None:
        return ""

    return (
        '<section class="debug">'
        '<h2>Debug</h2>'
        f'{_render_debug_claim_terms(debug_terms_by_claim)}'
        f'{_render_debug_terms_with_signs(debug_terms_with_signs)}'
        '</section>'
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
            "<tr>"
            f"<td>請求項{claim_number}</td>"
            f"<td>{escape(terms_text)}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="2">No extracted terms.</td></tr>')

    return (
        '<h3>抽出語句一覧</h3>'
        '<table>'
        '<thead><tr><th>Claim</th><th>Terms</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
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
        '<h3>符号付語句一覧</h3>'
        '<table>'
        '<thead><tr><th>Source</th><th>Whole</th><th>Term</th><th>Sign</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
    )
