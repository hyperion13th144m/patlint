"""Convert AI JSON response to Diagnostic objects."""
from __future__ import annotations

import json
import re
from typing import Any

from patent_checker_common.models import Diagnostic, DiagnosticLocation, Severity


_SEVERITY_MAP: dict[str, Severity] = {
    "high": "error",
    "medium": "warning",
    "low": "info",
}

_CLAIM_RE = re.compile(r"請求項\s*(\d+)")
_BRACKET_RE = re.compile(r"【([^】]+)】")
_PARA_ID_RE = re.compile(r"^\d{4}$")


def _to_fullwidth(text: str) -> str:
    """半角英数字・ハイフンを全角に変換する（段落番号・請求項番号の正規化用）。"""
    result = []
    for ch in text:
        if "0" <= ch <= "9":
            result.append(chr(ord(ch) - ord("0") + ord("０")))
        elif "A" <= ch <= "Z":
            result.append(chr(ord(ch) - ord("A") + ord("Ａ")))
        elif "a" <= ch <= "z":
            result.append(chr(ord(ch) - ord("a") + ord("ａ")))
        else:
            result.append(ch)
    return "".join(result)


def _location_to_search_text(location_str: str) -> str | None:
    """
    AI が返す location 文字列からブロック検索用の search_text を生成する。

    対応パターン:
      【請求項1】  →  【請求項１】  (全角化)
      【0030】    →  【０００３０】 (全角化)
      請求項2      →  【請求項２】  (隅付き括弧を補完)
      0030         →  【００３０】  (隅付き括弧を補完)
    """
    if not location_str:
        return None

    # 【...】 がそのまま含まれている場合は中身を全角化して返す
    m = _BRACKET_RE.search(location_str)
    if m:
        inner = _to_fullwidth(m.group(1))
        return f"【{inner}】"

    # 「請求項N」形式
    claim_m = _CLAIM_RE.search(location_str)
    if claim_m:
        n = _to_fullwidth(claim_m.group(1))
        return f"【請求項{n}】"

    # 4桁数字のみ（段落番号）
    stripped = location_str.strip()
    if re.fullmatch(r"\d{4}", stripped):
        return f"【{_to_fullwidth(stripped)}】"

    return None


def parse_ai_response(response_text: str) -> list[dict[str, Any]]:
    """Extract JSON from AI response, tolerating markdown code fences."""
    text = response_text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return data.get("issues", [])
    if isinstance(data, list):
        return data
    return []


def ai_issues_to_diagnostics(
    response_text: str,
    rule_id_prefix: str = "AI",
) -> list[Diagnostic]:
    issues = parse_ai_response(response_text)
    diagnostics: list[Diagnostic] = []

    for issue in issues:
        if not isinstance(issue, dict):
            continue

        severity_raw = str(issue.get("severity", "low")).lower()
        severity: Severity = _SEVERITY_MAP.get(severity_raw, "info")

        category = str(issue.get("category", "other"))
        rule_id = f"{rule_id_prefix}_{category.upper()}"

        message = str(issue.get("message", ""))
        if not message:
            continue

        suggestion = issue.get("suggestion")
        location_str = str(issue.get("location", ""))

        search_text = _location_to_search_text(location_str)

        location: DiagnosticLocation | None = None
        if search_text:
            claim_m = re.search(r"請求項([０-９\d]+)", search_text)
            if claim_m:
                # 全角数字を半角に戻して int 化
                num_str = claim_m.group(1).translate(
                    str.maketrans("０１２３４５６７８９", "0123456789")
                )
                location = DiagnosticLocation(
                    source_type="document",
                    section_type="claims",
                    claim_number=int(num_str),
                    search_text=search_text,
                )
            else:
                location = DiagnosticLocation(
                    source_type="document",
                    search_text=search_text,
                )
        elif location_str:
            location = DiagnosticLocation(source_type="document")

        reason = issue.get("reason") or None
        original_text = issue.get("original_text") or None

        diagnostics.append(
            Diagnostic(
                rule_id=rule_id,
                severity=severity,
                message=message,
                location=location,
                suggestion=str(suggestion) if suggestion else None,
                reason=str(reason) if reason else None,
                original_text=str(original_text) if original_text else None,
            )
        )

    return diagnostics
