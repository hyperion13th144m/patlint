from __future__ import annotations

from patent_checker_common import Diagnostic

from .common import _node_text, _paragraph_label, _paragraph_location, _paragraph_sentences


def check_paragraph_numbering(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    paragraphs = tree.find_all(kind="paragraph")
    if len(paragraphs) < 2:
        return []

    previous = paragraphs[0]
    for paragraph in paragraphs[1:]:
        if paragraph.number != previous.number + 1:
            return [
                Diagnostic(
                    rule_id="PARAGRAPH_NUMBERING",
                    severity="error",
                    message=(
                        f"段落番号は{previous.number}まで正しく連番ですが、"
                        "それ以降は連番ではありません。"
                    ),
                    location=_paragraph_location(paragraph),
                    suggestion="段落番号に抜けや重複がないか確認してください。",
                )
            ]
        previous = paragraph

    return []


def check_paragraph_end_punctuation(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    diagnostics: list[Diagnostic] = []
    for paragraph in tree.find_all(kind="paragraph"):
        text = _node_text(paragraph).rstrip()
        if not text or text.endswith("。"):
            continue
        diagnostics.append(
            Diagnostic(
                rule_id="PARAGRAPH_END_PUNCTUATION",
                severity="error",
                message="段落の末尾が句点「。」で終わっていません。",
                location=_paragraph_location(paragraph),
                suggestion="段落末尾を句点「。」で終えるよう確認してください。",
            )
        )

    return diagnostics


def check_missing_subject_in_embodiment_sentences(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    diagnostics: list[Diagnostic] = []
    for embodiment in tree.find_all(kind="description_of_embodiments"):
        for paragraph in embodiment.find_all(kind="paragraph"):
            paragraph_label = _paragraph_label(paragraph)
            for sentence in _paragraph_sentences(_node_text(paragraph)):
                if not sentence or any(particle in sentence for particle in ("は", "が", "も")):
                    continue
                diagnostics.append(
                    Diagnostic(
                        rule_id="MISSING_SUBJECT_IN_EMBODIMENT_SENTENCE",
                        severity="warning",
                        message=(
                            f"{paragraph_label}の文に主語が欠けている可能性があります。"
                        ),
                        location=_paragraph_location(paragraph),
                        suggestion="文中に主語を示す「は」「が」「も」が含まれているか確認してください。",
                    )
                )

    return diagnostics


def check_long_embodiment_sentences(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    diagnostics: list[Diagnostic] = []
    for embodiment in tree.find_all(kind="description_of_embodiments"):
        for paragraph in embodiment.find_all(kind="paragraph"):
            for sentence in _paragraph_sentences(_node_text(paragraph)):
                if len(sentence) < 200:
                    continue
                diagnostics.append(
                    Diagnostic(
                        rule_id="LONG_EMBODIMENT_SENTENCE",
                        severity="warning",
                        message=(
                            f"実施形態の一文が長すぎます（{len(sentence)}文字）。"
                        ),
                        location=_paragraph_location(paragraph),
                        suggestion="一文を200文字未満に分割できないか確認してください。",
                    )
                )

    return diagnostics
