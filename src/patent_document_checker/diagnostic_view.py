from __future__ import annotations

from collections.abc import Iterable

from patent_checker_common import Diagnostic, DiagnosticLocation

RULE_LABELS = {
    "ABSTRACT_LENGTH": "要約書文字数",
    "CLAIM_DEPENDENCY": "請求項引用",
    "CLAIM_NUMBERING": "請求項番号",
    "CLAIM_TERM_IN_EMBODIMENTS": "請求項語句（実施形態）",
    "CLAIM_TERM_IN_TECH_SOLUTION": "請求項語句（解決手段）",
    "CLAIM_TERM_REFERENCE_PREFIX": "前記ぬけ",
    "DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH": "従属請求項の発明名称",
    "FIGURE_REFERENCE": "図面番号引用",
    "FORBIDDEN_CHARACTER": "禁止文字",
    "INVENTION_TITLE_CLAIM_MISMATCH": "発明の名称と請求項",
    "LONG_EMBODIMENT_SENTENCE": "長すぎる一文",
    "MISSING_SUBJECT_IN_EMBODIMENT_SENTENCE": "主語候補",
    "MULTI_MULTI_CLAIM": "マルチマルチクレーム",
    "PARAGRAPH_END_PUNCTUATION": "段落末尾句点",
    "PARAGRAPH_NUMBERING": "段落番号",
    "SIGN_TERM_CONFLICT": "同一符号の語句不一致",
    "TERM_SIGN_CONFLICT": "同一語句の符号不一致",
    "TERM_VARIATION": "語句の表記揺れ",
}

SEVERITY_LABELS = {
    "error": "ERROR",
    "warning": "WARNING",
    "info": "INFO",
}

SECTION_LABELS = {
    "abstract": "要約書",
    "application_form": "特許願",
    "claims": "特許請求の範囲",
    "description": "明細書",
    "description_of_drawings": "図面の簡単な説明",
    "invention_title": "発明の名称",
    "paragraphs": "段落",
    "terms": "語句",
}


def diagnostics_to_views(diagnostics: Iterable[Diagnostic]) -> list[dict[str, str]]:
    return [diagnostic_to_view(diagnostic) for diagnostic in diagnostics]


def diagnostic_to_view(diagnostic: Diagnostic) -> dict:
    return {
        "severity": diagnostic.severity,
        "severity_label": SEVERITY_LABELS.get(diagnostic.severity, diagnostic.severity.upper()),
        "rule_id": diagnostic.rule_id,
        "rule_label": rule_label(diagnostic.rule_id),
        "message": diagnostic.message,
        "location": location_label(diagnostic.location),
        "location_data": location_data(diagnostic.location),
    }


def rule_label(rule_id: str) -> str:
    if rule_id.startswith("RECOMMENDED_WORDING_"):
        category = rule_id.removeprefix("RECOMMENDED_WORDING_").lower()
        return f"推奨されない語句（{category}）"
    return RULE_LABELS.get(rule_id, rule_id)


def location_label(location: DiagnosticLocation | None) -> str:
    if location is None:
        return "－"
    if location.claim_number is not None:
        return f"請求項{location.claim_number}"
    if location.search_text:
        return _normalize_search_text(location.search_text)
    if location.figure_id:
        return f"図{location.figure_id}"
    if location.section_type:
        return SECTION_LABELS.get(location.section_type, location.section_type)
    if location.block_index is not None:
        return f"ブロック{location.block_index + 1}"
    return "－"


def location_data(location: DiagnosticLocation | None) -> dict | None:
    if location is None:
        return None
    data: dict = {}
    if location.block_index is not None:
        data["block_index"] = location.block_index
    if location.section_type is not None:
        data["section_type"] = location.section_type
    if location.claim_number is not None:
        data["claim_number"] = location.claim_number
    if location.search_text is not None:
        data["search_text"] = location.search_text
    return data or None


def _normalize_search_text(search_text: str) -> str:
    if search_text.startswith("【") and search_text.endswith("】"):
        inner = search_text[1:-1]
        if inner.isdigit():
            return f"段落【{inner}】"
        return search_text
    return search_text
