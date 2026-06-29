"""Prompt builders for AI patent review."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """\
あなたは日本の特許明細書の校正者です。
あなたの役割は、特許明細書の品質向上のために、問題候補を指摘することです。

重要：
- 本文を勝手に全面修正しないでください。
- 指摘は「候補」として出してください。
- 最終判断は人間の弁理士・担当者が行います。
- 発明の内容を勝手に追加しないでください。
- 権利範囲を不用意に狭める修正案を出す場合は、そのリスクを明記してください。
- 不明な場合は断定せず、「確認推奨」としてください。
- 出力は指定されたJSONスキーマに従ってください。余計なテキストは出力しないでください。"""

_OVERVIEW_SCHEMA = {
    "invention_summary": "発明の概要（1〜3文）",
    "main_components": ["主要構成要素のリスト"],
    "claim_support_candidates": [
        {"claim_number": 1, "paragraph_ids": ["0030", "0031"]}
    ],
    "risk_focus": [
        {
            "message": "指摘内容（日本語）",
            "primary_location": "最も関連度の高い箇所を【請求項1】や【0030】のように隅付き括弧で1つだけ指定",
            "related_locations": [
                "補足的な関連箇所があれば【0031】のように列挙、なければ空配列"
            ],
        }
    ],
}

_ISSUES_SCHEMA = {
    "issues": [
        {
            "category": "claim_clarity | support | term_consistency | dependency | ambiguity | typo | syntax | other",
            "severity": "high | medium | low",
            "location": "必ず【請求項1】や【0030】のように隅付き括弧の見出しをそのまま使うこと。複数箇所の場合は最も関連度の高い一つを選ぶ。",
            "original_text": "問題箇所の原文（短く）",
            "message": "指摘内容（日本語）",
            "reason": "根拠（日本語）",
            "suggestion": "修正案（任意、日本語）",
            "confidence": 0.8,
        }
    ]
}

# 段落レビュー専用: location を対象段落の見出しに限定する
_PARA_ISSUES_SCHEMA = {
    "issues": [
        {
            "category": "typo | syntax | term_consistency | ambiguity | support | other",
            "severity": "high | medium | low",
            "location": "必ず対象段落の見出し（例：【0030】）を使うこと。請求項番号を location に使ってはいけない。",
            "original_text": "問題箇所の原文（短く）",
            "message": "指摘内容（日本語）",
            "reason": "根拠（日本語）",
            "suggestion": "修正案（任意、日本語）",
            "confidence": 0.8,
        }
    ]
}


def build_overview_prompt(
    full_text: str,
    claims_text: str,
    signs_text: str,
    terms_text: str,
) -> str:
    return f"""\
以下は特許明細書の全文です。発明の概要を把握し、請求項と実施形態の対応候補、重点チェック箇所を抽出してください。

## 明細書全文
{full_text}

## 請求項
{claims_text}

## 符号説明
{signs_text}

## 主要用語
{terms_text}

以下のJSONスキーマで回答してください：
{json.dumps(_OVERVIEW_SCHEMA, ensure_ascii=False, indent=2)}"""


def build_claim_review_prompt(
    claim_number: int,
    claim_text: str,
    referenced_claim_texts: list[str],
    description_paragraphs: list[str],
    signs_text: str,
    terms_text: str,
    rule_issues: list[dict[str, Any]],
    overview_summary: str | None = None,
    overview_risk_focus: list[str] | None = None,
) -> str:
    refs = "\n".join(referenced_claim_texts) if referenced_claim_texts else "（なし）"
    paragraphs = (
        "\n\n".join(description_paragraphs) if description_paragraphs else "（なし）"
    )
    rule_issues_text = (
        json.dumps(rule_issues, ensure_ascii=False, indent=2)
        if rule_issues
        else "（なし）"
    )
    overview_section = ""
    if overview_summary or overview_risk_focus:
        lines = ["## 全体レビューからのコンテキスト（参考）"]
        if overview_summary:
            lines.append(f"発明の概要：{overview_summary}")
        if overview_risk_focus:
            lines.append("重点チェック箇所：")
            lines.extend(f"- {item}" for item in overview_risk_focus)
        overview_section = "\n".join(lines) + "\n\n"

    return f"""\
以下の請求項{claim_number}について、明確性・実施形態サポート・用語整合性・係り受けなどの観点からチェックしてください。

{overview_section}## 対象請求項
{claim_text}

## 引用元請求項
{refs}

## 関連する実施形態段落
{paragraphs}

## 符号説明
{signs_text}

## 主要用語一覧
{terms_text}

## ルールベースチェック結果（参考）
{rule_issues_text}

チェック観点：
- 明確性（特許法第36条第6項第2号）
- 実施形態サポート（特許法第36条第6項第1号）
- 用語整合性（請求項内・明細書との一致）
- 構成要件の対応
- 不明確表現候補
- 請求項の係り受け
- 過度な限定の可能性
- 実施形態にしかない構成が請求項に入っていないか、その逆

以下のJSONスキーマで回答してください：
{json.dumps(_ISSUES_SCHEMA, ensure_ascii=False, indent=2)}"""


PROOFREAD_SYSTEM_PROMPT = """\
あなたは日本語文書の校正者です。
指定された段落を「誤字脱字」「係り受け」の観点のみで校正してください。

ルール：
- 発明の内容・構成は一切変えないでください。
- 最小限の修正のみ行ってください。
- 修正箇所がなければ {"has_correction": false} のみ返してください。
- 修正箇所がある場合は {"has_correction": true, "corrected_text": "段落全文（修正済み）"} を返してください。
- corrected_text には段落の全文を入れてください（修正箇所だけではなく）。
- 余計なテキストは出力しないでください。"""


def build_proofread_prompt(block_text: str) -> str:
    return f"""\
以下の段落を誤字脱字・係り受けの観点で校正してください。

## 対象段落
{block_text}

修正がなければ {{"has_correction": false}}、修正がある場合は {{"has_correction": true, "corrected_text": "段落全文（修正済み）"}} を返してください。"""


def build_paragraph_review_prompt(
    target_paragraph: str,
    context_paragraphs: list[str],
    section_type: str,
    related_claims: list[str],
    signs_text: str,
    rule_issues: list[dict[str, Any]],
    overview_summary: str | None = None,
    overview_risk_focus: list[str] | None = None,
) -> str:
    ctx = "\n\n".join(context_paragraphs) if context_paragraphs else "（なし）"
    claims = "\n".join(related_claims) if related_claims else "（なし）"
    rule_issues_text = (
        json.dumps(rule_issues, ensure_ascii=False, indent=2)
        if rule_issues
        else "（なし）"
    )
    overview_section = ""
    if overview_summary or overview_risk_focus:
        lines = ["## 全体レビューからのコンテキスト（参考）"]
        if overview_summary:
            lines.append(f"発明の概要：{overview_summary}")
        if overview_risk_focus:
            lines.append("重点チェック箇所：")
            lines.extend(f"- {item}" for item in overview_risk_focus)
        overview_section = "\n".join(lines) + "\n\n"

    return f"""\
以下の段落（セクション種別：{section_type}）について、誤字脱字・係り受け・表記ゆれ・前記表現・不明確表現などをチェックしてください。

注意：前後の段落は隣接する一部のみを参考として提供しています。他の段落が含まれていなくても問題ではありません。段落の欠番や他段落の内容不在については指摘しないでください。

{overview_section}## 対象段落
{target_paragraph}

## 前後の段落（文脈・参考）
{ctx}

## 関連する請求項
{claims}

## 符号説明
{signs_text}

## ルールベースチェック結果（参考）
{rule_issues_text}

チェック観点：
- 誤字脱字
- 日本語の係り受け
- 表記ゆれ
- 前記の不自然な使用
- 不明確表現
- 特許明細書として不適切な断定表現
- 請求項と矛盾しそうな表現

以下のJSONスキーマで回答してください（locationには必ず対象段落の見出しを使い、請求項番号は使わないこと）：
{json.dumps(_PARA_ISSUES_SCHEMA, ensure_ascii=False, indent=2)}"""
