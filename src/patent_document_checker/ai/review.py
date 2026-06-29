"""High-level review functions that orchestrate AI calls."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from patent_checker_common.models import Diagnostic, DiagnosticLocation

from ..parser import PatentDocumentIR
from .anonymizer import anonymize
from .client import AIClient, TokenUsage
from .converter import ai_issues_to_diagnostics, parse_ai_response
from .prompts import (
    PROOFREAD_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_claim_review_prompt,
    build_overview_prompt,
    build_paragraph_review_prompt,
    build_proofread_prompt,
)

_MAX_CONTEXT_CHARS = 600  # コンテキスト段落1件あたりの上限
_MAX_FULL_TEXT_CHARS = 12000

# 段落番号【NNNN】を抽出する正規表現
_PARA_ID_RE = re.compile(r"【(\d{4})】")


@dataclass
class RiskFocusItem:
    message: str
    primary_location: str | None = None        # 例: "【請求項１】"
    related_locations: list[str] = field(default_factory=list)  # 例: ["【０００３０】"]


@dataclass
class OverviewResult:
    """全体レビューの構造化結果。請求項・段落レビューに引き継ぐ。"""
    invention_summary: str = ""
    main_components: list[str] = field(default_factory=list)
    # claim_number -> paragraph_ids (["0030", "0031"])
    claim_support_candidates: dict[int, list[str]] = field(default_factory=dict)
    risk_focus: list[RiskFocusItem] = field(default_factory=list)

    @property
    def risk_focus_messages(self) -> list[str]:
        return [item.message for item in self.risk_focus]

    def to_dict(self) -> dict[str, Any]:
        return {
            "invention_summary": self.invention_summary,
            "main_components": self.main_components,
            "claim_support_candidates": [
                {"claim_number": k, "paragraph_ids": v}
                for k, v in self.claim_support_candidates.items()
            ],
            "risk_focus": [
                {
                    "message": r.message,
                    "primary_location": r.primary_location,
                    "related_locations": r.related_locations,
                }
                for r in self.risk_focus
            ],
        }


def _parse_risk_focus_item(item: object) -> RiskFocusItem | None:
    """risk_focus の要素（文字列またはオブジェクト）を RiskFocusItem に変換する。"""
    if isinstance(item, str):
        return RiskFocusItem(message=item) if item.strip() else None
    if isinstance(item, dict):
        message = str(item.get("message") or item.get("description") or item.get("item") or "")
        if not message.strip():
            return None
        primary = item.get("primary_location") or item.get("location") or None
        related_raw = item.get("related_locations") or []
        related = [str(r) for r in related_raw if r] if isinstance(related_raw, list) else []
        return RiskFocusItem(
            message=message,
            primary_location=str(primary) if primary else None,
            related_locations=related,
        )
    return None


def _parse_overview_response(response_text: str) -> OverviewResult:
    """全体レビューのJSONレスポンスを OverviewResult に変換する。"""
    text = response_text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return OverviewResult()

    if not isinstance(data, dict):
        return OverviewResult()

    candidates: dict[int, list[str]] = {}
    for item in data.get("claim_support_candidates", []):
        if isinstance(item, dict):
            num = item.get("claim_number")
            ids = item.get("paragraph_ids", [])
            if isinstance(num, int) and isinstance(ids, list):
                candidates[num] = [str(i) for i in ids]

    return OverviewResult(
        invention_summary=str(data.get("invention_summary", "")),
        main_components=[str(c) for c in data.get("main_components", []) if c],
        claim_support_candidates=candidates,
        risk_focus=[
            item for r in data.get("risk_focus", [])
            if r and (item := _parse_risk_focus_item(r)) is not None
        ],
    )


def _overview_to_diagnostics(overview: OverviewResult) -> list[Diagnostic]:
    """risk_focus の各項目を info レベルの Diagnostic に変換する。"""
    from .converter import _location_to_search_text

    diagnostics: list[Diagnostic] = []
    for item in overview.risk_focus:
        search_text = (
            _location_to_search_text(item.primary_location)
            if item.primary_location
            else "【全体】"
        )
        # 関連箇所があればメッセージに追記
        message = item.message
        if item.related_locations:
            related = "、".join(item.related_locations)
            message = f"{message}（関連: {related}）"

        # claim_number を search_text から取り出す
        claim_number: int | None = None
        if search_text:
            import re as _re
            m = _re.search(r"請求項([０-９\d]+)", search_text)
            if m:
                num_str = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
                claim_number = int(num_str)

        diagnostics.append(
            Diagnostic(
                rule_id="AI_OVERVIEW_RISK",
                severity="info",
                message=message,
                location=DiagnosticLocation(
                    source_type="document",
                    section_type="claims" if claim_number else None,
                    claim_number=claim_number,
                    search_text=search_text,
                ),
            )
        )
    return diagnostics


def _blocks_text(document: PatentDocumentIR, section: str | None = None) -> str:
    blocks = document.raw_blocks
    if section:
        blocks = [b for b in blocks if b.section_type == section]
    return "\n".join(b.text for b in blocks)


def _description_paragraphs(document: PatentDocumentIR) -> list[str]:
    return [
        b.text
        for b in document.raw_blocks
        if b.section_type == "description" and len(b.text) > 10
    ]


def _paragraphs_by_ids(document: PatentDocumentIR, paragraph_ids: list[str]) -> list[str]:
    """overview の paragraph_ids（"0030" 形式）に対応する段落テキストを返す。"""
    id_set = set(paragraph_ids)
    result = []
    for block in document.raw_blocks:
        m = _PARA_ID_RE.search(block.text)
        if m and m.group(1) in id_set:
            result.append(block.text)
    return result


def _signs_text(document: PatentDocumentIR) -> str:
    from ..report.reference_signs import reference_sign_entries
    from ..terms import extract_document_terms_with_signs

    try:
        tws = extract_document_terms_with_signs(document.tree)
        entries = reference_sign_entries(tws)
        return "\n".join(
            f"{e.get('sign', '')}：{e.get('term', '')}" for e in entries
        )
    except Exception:
        return ""


def _terms_text(document: PatentDocumentIR) -> str:
    from ..terms import extract_term_occurrences

    try:
        occurrences = extract_term_occurrences(document.claims, document.tree)
        terms = sorted({o.get("term", "") for o in occurrences if o.get("term")})
        return "、".join(terms[:60])
    except Exception:
        return ""


def _diagnostics_to_dicts(diagnostics: list[Diagnostic]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": d.rule_id,
            "severity": d.severity,
            "message": d.message,
            "location": d.location.to_dict() if d.location else None,
        }
        for d in diagnostics
    ]


async def overview_review(
    document: PatentDocumentIR,
    client: AIClient,
    rule_diagnostics: list[Diagnostic] | None = None,
    do_anonymize: bool = True,
) -> tuple[list[Diagnostic], OverviewResult, TokenUsage]:
    """全体レビュー。Diagnostic リスト、OverviewResult、トークン使用量を返す。"""
    full_text = _blocks_text(document)[:_MAX_FULL_TEXT_CHARS]
    claims_text = _blocks_text(document, section="claims")
    signs_text = _signs_text(document)
    terms_text = _terms_text(document)

    if do_anonymize:
        full_text, _ = anonymize(full_text)
        claims_text, _ = anonymize(claims_text)

    user_prompt = build_overview_prompt(full_text, claims_text, signs_text, terms_text)
    response, usage = await client.chat(SYSTEM_PROMPT, user_prompt)

    overview = _parse_overview_response(response)
    diagnostics = _overview_to_diagnostics(overview)
    return diagnostics, overview, usage


async def iter_claim_review(
    document: PatentDocumentIR,
    claim_numbers: list[int],
    client: AIClient,
    rule_diagnostics: list[Diagnostic] | None = None,
    do_anonymize: bool = True,
    overview: OverviewResult | None = None,
) -> AsyncGenerator[tuple[str, list[Diagnostic], TokenUsage], None]:
    """請求項ごとに (ラベル, diagnostics, usage) を yield する async generator。"""
    signs_text = _signs_text(document)
    terms_text = _terms_text(document)
    claim_map = {c.number: c for c in document.claims}

    for claim_number in claim_numbers:
        claim = claim_map.get(claim_number)
        if claim is None:
            continue

        if overview and claim_number in overview.claim_support_candidates:
            paragraph_ids = overview.claim_support_candidates[claim_number]
            description_paragraphs = _paragraphs_by_ids(document, paragraph_ids)
            if not description_paragraphs:
                description_paragraphs = _description_paragraphs(document)[:20]
        else:
            description_paragraphs = _description_paragraphs(document)[:20]

        claim_text = claim.text
        referenced_texts = [
            claim_map[n].text
            for n in claim.referenced_claims
            if n in claim_map
        ]

        claim_rule_issues: list[dict[str, Any]] = []
        if rule_diagnostics:
            claim_rule_issues = [
                d
                for d in _diagnostics_to_dicts(rule_diagnostics)
                if (d.get("location") or {}).get("claim_number") == claim_number
            ]

        if do_anonymize:
            claim_text, _ = anonymize(claim_text)
            referenced_texts = [anonymize(t)[0] for t in referenced_texts]

        user_prompt = build_claim_review_prompt(
            claim_number=claim_number,
            claim_text=claim_text,
            referenced_claim_texts=referenced_texts,
            description_paragraphs=description_paragraphs,
            signs_text=signs_text,
            terms_text=terms_text,
            rule_issues=claim_rule_issues,
            overview_summary=overview.invention_summary if overview else None,
            overview_risk_focus=overview.risk_focus_messages if overview else None,
        )
        response, usage = await client.chat(SYSTEM_PROMPT, user_prompt)
        diagnostics = ai_issues_to_diagnostics(response, rule_id_prefix="AI_CLAIM")
        yield f"請求項{claim_number}", diagnostics, usage


async def claim_review(
    document: PatentDocumentIR,
    claim_numbers: list[int],
    client: AIClient,
    rule_diagnostics: list[Diagnostic] | None = None,
    do_anonymize: bool = True,
    overview: OverviewResult | None = None,
) -> tuple[list[Diagnostic], TokenUsage]:
    """iter_claim_review のバッチラッパー。"""
    all_diagnostics: list[Diagnostic] = []
    total_usage: TokenUsage = {"input_tokens": 0, "output_tokens": 0}
    async for _, diagnostics, usage in iter_claim_review(
        document, claim_numbers, client, rule_diagnostics, do_anonymize, overview
    ):
        all_diagnostics.extend(diagnostics)
        total_usage["input_tokens"] += usage["input_tokens"]
        total_usage["output_tokens"] += usage["output_tokens"]
    return all_diagnostics, total_usage


async def iter_paragraph_review(
    document: PatentDocumentIR,
    block_indices: list[int],
    client: AIClient,
    rule_diagnostics: list[Diagnostic] | None = None,
    do_anonymize: bool = True,
    overview: OverviewResult | None = None,
) -> AsyncGenerator[tuple[str, list[Diagnostic], TokenUsage], None]:
    """段落ごとに (ラベル, diagnostics, usage) を yield する async generator。"""
    signs_text = _signs_text(document)
    blocks = document.raw_blocks
    index_map = {b.index: b for b in blocks}
    claims_texts = [c.text for c in document.claims]

    for idx in block_indices:
        block = index_map.get(idx)
        if block is None:
            continue

        target_text = block.text
        section_type = block.section_type or "unknown"

        context = [
            index_map[i].text
            for i in range(max(0, idx - 2), idx + 3)
            if i != idx and i in index_map
        ]

        block_rule_issues: list[dict[str, Any]] = []
        if rule_diagnostics:
            block_rule_issues = [
                d
                for d in _diagnostics_to_dicts(rule_diagnostics)
                if (d.get("location") or {}).get("block_index") == idx
            ]

        if do_anonymize:
            target_text, _ = anonymize(target_text)

        # ブロックヘッダー（【NNNN】など）をラベルに使う
        header_m = re.match(r"(【[^】]+】)", target_text)
        label = header_m.group(1) if header_m else f"ブロック{idx}"

        user_prompt = build_paragraph_review_prompt(
            target_paragraph=target_text,
            context_paragraphs=[c[:_MAX_CONTEXT_CHARS] for c in context],
            section_type=section_type,
            related_claims=claims_texts[:5],
            signs_text=signs_text,
            rule_issues=block_rule_issues,
            overview_summary=overview.invention_summary if overview else None,
            overview_risk_focus=overview.risk_focus_messages if overview else None,
        )
        response, usage = await client.chat(SYSTEM_PROMPT, user_prompt)
        diagnostics = ai_issues_to_diagnostics(response, rule_id_prefix="AI_PARA")
        yield label, diagnostics, usage


async def paragraph_review(
    document: PatentDocumentIR,
    block_indices: list[int],
    client: AIClient,
    rule_diagnostics: list[Diagnostic] | None = None,
    do_anonymize: bool = True,
    overview: OverviewResult | None = None,
) -> tuple[list[Diagnostic], TokenUsage]:
    """iter_paragraph_review のバッチラッパー。"""
    all_diagnostics: list[Diagnostic] = []
    total_usage: TokenUsage = {"input_tokens": 0, "output_tokens": 0}
    async for _, diagnostics, usage in iter_paragraph_review(
        document, block_indices, client, rule_diagnostics, do_anonymize, overview
    ):
        all_diagnostics.extend(diagnostics)
        total_usage["input_tokens"] += usage["input_tokens"]
        total_usage["output_tokens"] += usage["output_tokens"]
    return all_diagnostics, total_usage


def _parse_proofread_response(response_text: str) -> tuple[bool, str | None]:
    text = response_text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False, None
    if not isinstance(data, dict):
        return False, None
    has_correction = bool(data.get("has_correction", False))
    corrected = data.get("corrected_text") if has_correction else None
    return has_correction, str(corrected) if corrected else None


def _deanonymize(text: str, mapping: dict[str, str]) -> str:
    """anonymize() のマッピングを逆引きして元のテキストに戻す。"""
    reverse = {v: k for k, v in mapping.items()}
    for placeholder, original in reverse.items():
        text = text.replace(placeholder, original)
    return text


_HEADER_RE = re.compile(r"^【[^】]+】")


def _group_blocks(document: PatentDocumentIR) -> list[tuple[str, str]]:
    """【...】ブロックを起点に、直後の非ヘッダーブロックを結合してグループ化する。

    Returns: list of (label, combined_text)
    """
    blocks = document.raw_blocks
    groups: list[tuple[str, str]] = []
    i = 0
    while i < len(blocks):
        text = blocks[i].text
        m = _HEADER_RE.match(text)
        if not m:
            i += 1
            continue
        label = m.group(0)
        parts = [text]
        j = i + 1
        while j < len(blocks):
            next_text = blocks[j].text
            if _HEADER_RE.match(next_text):
                break
            if next_text:
                parts.append(next_text)
            j += 1
        i = j
        combined = "\n".join(parts)
        groups.append((label, combined))
    return groups


async def iter_proofread(
    document: PatentDocumentIR,
    client: AIClient,
    do_anonymize: bool = True,
) -> AsyncGenerator[tuple[str, bool, str, str | None, TokenUsage], None]:
    """グループ（【...】〜次の【...】）ごとに (label, has_correction, original_text, corrected_text, usage) を yield。"""
    for label, combined_text in _group_blocks(document):
        if len(combined_text) < 10:
            continue

        send_text = combined_text
        amap: dict[str, str] | None = None
        if do_anonymize:
            send_text, amap_obj = anonymize(combined_text)
            amap = amap_obj.mapping

        user_prompt = build_proofread_prompt(send_text)
        response, usage = await client.chat(PROOFREAD_SYSTEM_PROMPT, user_prompt)

        has_correction, corrected = _parse_proofread_response(response)
        if has_correction and corrected and amap:
            corrected = _deanonymize(corrected, amap)

        yield label, has_correction, combined_text, corrected, usage
