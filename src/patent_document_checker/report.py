from __future__ import annotations

from html import escape

from patent_checker_common import DiagnosticsResult


def render_html_report(result: DiagnosticsResult) -> str:
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
</body>
</html>
"""
