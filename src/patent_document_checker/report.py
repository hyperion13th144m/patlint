from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from html import escape

from patent_checker_common import DiagnosticsResult

_FULLWIDTH_ASCII = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "０１２３４５６７８９",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
)
_SIGN_TRANSLATION = str.maketrans(
    {
        "－": "-",
        "ー": "-",
        "―": "-",
        "‐": "-",
        "’": "'",
        "＇": "'",
    }
)


def render_html_report(
    result: DiagnosticsResult,
    term_occurrences: Mapping[str, Sequence[str]] | None = None,
    terms_with_signs: Sequence[object] | None = None,
    claims: Sequence[object] | None = None,
    unit_checks: Sequence[object] | None = None,
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
    term_occurrences_html = _render_term_occurrences(term_occurrences)
    claim_relationships_html = _render_claim_relationships(claims)
    unit_checks_html = _render_unit_checks(unit_checks)
    reference_sign_list_html = _render_reference_sign_list(terms_with_signs)
    debug_terms_html = _render_debug_terms(debug_terms_by_claim, debug_terms_with_signs)
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
    section {{ margin-top: 28px; }}
    .reference-controls {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin: 12px 0; }}
    .reference-controls label {{ display: grid; gap: 4px; color: #4b5563; font-size: 13px; }}
    .reference-controls select {{ min-height: 34px; border: 1px solid #d1d5db; border-radius: 4px; padding: 4px 8px; background: #ffffff; }}
    .reference-controls .check {{ display: flex; align-items: center; gap: 6px; min-height: 34px; }}
    .reference-output {{ white-space: pre-wrap; word-break: break-word; border: 1px solid #d1d5db; border-radius: 4px; background: #f9fafb; padding: 12px; line-height: 1.9; font-family: "Yu Gothic", "Meiryo", sans-serif; }}
    .copy-button {{ min-height: 34px; border: 1px solid #1f6f5b; border-radius: 4px; padding: 4px 12px; background: #1f6f5b; color: #ffffff; cursor: pointer; }}
    .copy-state {{ color: #4b5563; font-size: 13px; min-height: 20px; }}
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
  {term_occurrences_html}
  {claim_relationships_html}
  {unit_checks_html}
  {reference_sign_list_html}
  {debug_terms_html}
</body>
</html>
"""


def _render_claim_relationships(claims: Sequence[object] | None) -> str:
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


def _render_unit_checks(unit_checks: Sequence[object] | None) -> str:
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


def _render_reference_sign_list(terms_with_signs: Sequence[object] | None) -> str:
    if terms_with_signs is None:
        return ""

    entries_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for item in terms_with_signs:
        sign = str(getattr(item, "sign", "") or "").strip()
        term = str(getattr(item, "term", "") or "").strip()
        source = str(getattr(item, "source", "") or "").strip()
        if not sign or not term:
            continue
        key = (_normalize_sign_for_sort(sign), term)
        if key not in entries_by_key:
            entries_by_key[key] = {"sign": sign, "term": term, "source": source}
        elif source and source not in entries_by_key[key]["source"].split("、"):
            entries_by_key[key]["source"] = "、".join(
                value for value in [entries_by_key[key]["source"], source] if value
            )

    entries = sorted(
        entries_by_key.values(),
        key=lambda entry: _sign_sort_key(entry["sign"]),
    )
    data = json.dumps(entries, ensure_ascii=False).replace("</", "<\\/")

    rows = []
    for entry in entries:
        rows.append(
            "<tr>"
            f"<td>{escape(entry['sign'])}</td>"
            f"<td>{escape(entry['term'])}</td>"
            f"<td>{escape(entry['source'])}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="3">No signed terms.</td></tr>')

    return f"""
<section class="reference-sign-list">
  <h2>符号の説明用一覧</h2>
  <div class="reference-controls">
    <label>連結記号
      <select id="reference-joiner">
        <option value="…" selected>三点リーダ</option>
        <option value="　">空白</option>
      </select>
    </label>
    <label>区切り文字
      <select id="reference-separator">
        <option value="、">読点（、）</option>
        <option value="，" selected>カンマ（，）</option>
        <option value="__newline__">改行</option>
      </select>
    </label>
    <label>符号
      <select id="reference-width">
        <option value="full" selected>全角</option>
        <option value="half">半角</option>
      </select>
    </label>
    <label class="check"><input type="checkbox" id="reference-sort" checked> 昇順にソート</label>
    <button type="button" class="copy-button" id="reference-copy">コピー</button>
  </div>
  <div class="reference-output" id="reference-output"></div>
  <div class="copy-state" id="reference-copy-state"></div>
  <h3>抽出元</h3>
  <table>
    <thead><tr><th>符号</th><th>語句</th><th>出現場所</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  <script type="application/json" id="reference-sign-data">{data}</script>
  <script>
    (() => {{
      const data = JSON.parse(document.querySelector("#reference-sign-data").textContent);
      const output = document.querySelector("#reference-output");
      const state = document.querySelector("#reference-copy-state");
      const selected = id => document.querySelector(id).value;
      const normalizeSign = value => value
        .replace(/[Ａ-Ｚａ-ｚ０-９]/g, char => String.fromCharCode(char.charCodeAt(0) - 0xFEE0))
        .replace(/[－ー―‐]/g, "-")
        .replace(/[’＇]/g, "'")
        .replace(/[　\\s]+/g, "")
        .toUpperCase();
      const toFullWidth = value => value
        .replace(/[A-Za-z0-9]/g, char => String.fromCharCode(char.charCodeAt(0) + 0xFEE0))
        .replace(/-/g, "－")
        .replace(/'/g, "’");
      const toHalfWidth = value => value
        .replace(/[Ａ-Ｚａ-ｚ０-９]/g, char => String.fromCharCode(char.charCodeAt(0) - 0xFEE0))
        .replace(/[－ー―‐]/g, "-")
        .replace(/[’＇]/g, "'");
      const restRank = rest => {{
        if (!rest) return 0;
        if (/^[A-ZＡ-Ｚａ-ｚぁ-んァ-ヶ]/.test(rest)) return 1;
        if (/^-/.test(rest)) return 2;
        return 3;
      }};
      const signRank = sign => {{
        const normalized = normalizeSign(sign);
        const match = normalized.match(/^([A-Z]+)?(?:-)?(\\d+)?(.*)$/);
        if (!match) return [3, normalized];
        const letters = match[1] || "";
        const number = match[2] ? Number(match[2]) : null;
        const rest = match[3] || "";
        if (letters && number === null) return [0, letters, rest];
        if (letters && number !== null) return [0, letters, 0, number, rest];
        if (number !== null) return [1, number, restRank(rest), rest];
        return [2, normalized];
      }};
      const compareRank = (left, right) => {{
        const max = Math.max(left.length, right.length);
        for (let i = 0; i < max; i += 1) {{
          if (left[i] === right[i]) continue;
          if (left[i] === undefined) return -1;
          if (right[i] === undefined) return 1;
          if (typeof left[i] === "number" && typeof right[i] === "number") return left[i] - right[i];
          return String(left[i]).localeCompare(String(right[i]), "ja", {{ numeric: true }});
        }}
        return 0;
      }};
      const render = () => {{
        const joiner = selected("#reference-joiner");
        const separator = selected("#reference-separator") === "__newline__" ? "\\n" : selected("#reference-separator");
        const width = selected("#reference-width");
        const items = data.map((entry, index) => ({{ ...entry, index }}));
        if (document.querySelector("#reference-sort").checked) {{
          items.sort((a, b) => compareRank(signRank(a.sign), signRank(b.sign)) || a.index - b.index);
        }}
        output.textContent = items.map(entry => {{
          const sign = width === "full" ? toFullWidth(entry.sign) : toHalfWidth(entry.sign);
          return `${{sign}}${{joiner}}${{entry.term}}`;
        }}).join(separator);
        state.textContent = "";
      }};
      document.querySelectorAll("#reference-joiner, #reference-separator, #reference-width, #reference-sort")
        .forEach(element => element.addEventListener("change", render));
      document.querySelector("#reference-copy").addEventListener("click", async () => {{
        if (!output.textContent) return;
        try {{
          await navigator.clipboard.writeText(output.textContent);
        }} catch (error) {{
          const helper = document.createElement("textarea");
          helper.value = output.textContent;
          helper.style.position = "fixed";
          helper.style.opacity = "0";
          document.body.append(helper);
          helper.select();
          document.execCommand("copy");
          helper.remove();
        }}
        state.textContent = "コピーしました";
      }});
      render();
    }})();
  </script>
</section>
"""


def _normalize_sign_for_sort(sign: str) -> str:
    return (
        sign.translate(_SIGN_TRANSLATION)
        .translate(_FULLWIDTH_ASCII)
        .replace(" ", "")
        .replace("　", "")
        .upper()
    )


def _sign_sort_key(sign: str) -> tuple[object, ...]:
    normalized = _normalize_sign_for_sort(sign)
    match = re.match(r"^([A-Z]+)?(?:-)?(\d+)?(.*)$", normalized)
    if match is None:
        return (3, normalized)

    letters = match.group(1) or ""
    number = int(match.group(2)) if match.group(2) else None
    rest = match.group(3) or ""

    if letters and number is None:
        return (0, letters, rest)
    if letters and number is not None:
        return (0, letters, 0, number, rest)
    if number is not None:
        return (1, number, _sign_rest_rank(rest), rest)
    return (2, normalized)


def _sign_rest_rank(rest: str) -> int:
    if not rest:
        return 0
    if re.match(r"^[A-ZＡ-Ｚａ-ｚぁ-んァ-ヶ]", rest):
        return 1
    if rest.startswith("-"):
        return 2
    return 3


def _render_term_occurrences(
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


def _render_debug_terms(
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
