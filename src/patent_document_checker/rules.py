from __future__ import annotations

from collections import Counter
import re
import unicodedata

from patent_checker_common import Diagnostic, DiagnosticLocation

from .parser import Claim, PatentDocumentIR, RawBlock
from .terms import (
    extract_claim_term_occurrences,
    extract_claim_terms,
    extract_document_terms_with_signs,
    normalize_term_text,
)

# JPO's JIS X 0208 table displays these glyphs, while Python's strict
# shift_jis codec accepts their alternate Unicode mappings instead.
JPO_ALLOWED_SHIFT_JIS_VARIANTS = frozenset({"～", "－", "∥", "￢", "￠", "￡", "￤"})


def run_document_rules(document: PatentDocumentIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_forbidden_characters(document.raw_blocks))
    diagnostics.extend(check_paragraph_numbering(document.tree))
    diagnostics.extend(check_claim_numbering(document.claims))
    diagnostics.extend(check_claim_dependency(document.claims))
    diagnostics.extend(check_multi_multi_claim(document.claims))
    diagnostics.extend(check_missing_claim_term_reference_prefix(document.claims))
    diagnostics.extend(check_term_variations(document.claims, document.tree))
    diagnostics.extend(check_term_sign_conflicts(document.tree))
    diagnostics.extend(check_claim_terms_in_embodiments(document.claims, document.tree))
    diagnostics.extend(check_claim_terms_in_tech_solution(document.claims, document.tree))
    diagnostics.extend(check_long_embodiment_sentences(document.tree))
    return diagnostics


def check_forbidden_characters(blocks: list[RawBlock]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[int, str, str]] = set()

    for block in blocks:
        for char_index, char in enumerate(block.text):
            reason = _forbidden_character_reason(char)
            if reason is None:
                continue

            key = (block.index, char, reason)
            if key in seen:
                continue
            seen.add(key)

            diagnostics.append(
                Diagnostic(
                    rule_id="FORBIDDEN_CHARACTER",
                    severity="error",
                    message=(
                        f"使用できない文字 {char} が含まれています"
                        f"（{reason}、位置: {char_index + 1}文字目）。"
                    ),
                    location=DiagnosticLocation(
                        source_type="document",
                        section_type=block.section_type,
                        block_index=block.index,
                        search_text=char,
                    ),
                    suggestion=(
                        "JIS X 0208:1997に準拠したShift_JISで使用できる文字に置き換えてください。"
                    ),
                )
            )

    return diagnostics


def _forbidden_character_reason(char: str) -> str | None:
    if char in "\r\n":
        return None
    if _is_circled_number(char):
        return "丸付数字"
    if _is_halfwidth_katakana(char):
        return "半角カナ"
    if char == "\u20dd":
        return "合成用丸"
    if _is_disallowed_ascii_control(char):
        return "ASCII制御文字"
    if char in JPO_ALLOWED_SHIFT_JIS_VARIANTS:
        return None

    try:
        char.encode("shift_jis")
    except UnicodeEncodeError:
        return "Shift_JISに変換できない文字"

    return None


def _is_circled_number(char: str) -> bool:
    name = unicodedata.name(char, "")
    return "CIRCLED DIGIT" in name or "CIRCLED NUMBER" in name


def _is_halfwidth_katakana(char: str) -> bool:
    codepoint = ord(char)
    return 0xFF61 <= codepoint <= 0xFF9F


def _is_disallowed_ascii_control(char: str) -> bool:
    codepoint = ord(char)
    return codepoint < 0x20 or codepoint == 0x7F


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


def check_missing_claim_term_reference_prefix(claims: list[Claim]) -> list[Diagnostic]:
    by_number = {claim.number: claim for claim in claims}
    terms_by_claim = {
        claim.number: extract_claim_term_occurrences(claim.text) for claim in claims
    }
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        seen_terms = set(_referenced_claim_terms(claim, by_number, terms_by_claim))
        reported_terms: set[str] = set()

        for occurrence in terms_by_claim[claim.number]:
            if (
                occurrence.term in seen_terms
                and not occurrence.has_reference_prefix
                and not _is_claim_category_term_occurrence(claim.text, occurrence.start)
                and occurrence.term not in reported_terms
            ):
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_TERM_REFERENCE_PREFIX",
                        severity="warning",
                        message=(
                            f"請求項{claim.number}の語句 {occurrence.term} は、"
                            "2回目以降または引用元の請求項で出現済みですが、"
                            "前記・該・当該が付いていません（前記ぬけ）。"
                        ),
                        location=_claim_location(claim),
                        suggestion="2回目以降の語句には前記・該・当該を付けるか、語句の使い方を確認してください。",
                    )
                )
                reported_terms.add(occurrence.term)

            seen_terms.add(occurrence.term)

    return diagnostics


def _is_claim_category_term_occurrence(claim_text: str, occurrence_start: int) -> bool:
    normalized = normalize_term_text(claim_text)
    before = normalized[:occurrence_start]
    phrase = before.rsplit("。", maxsplit=1)[-1]
    return re.search(r"請求項.{0,40}に記載(?:の|する|された)$", phrase) is not None


def _referenced_claim_terms(
    claim: Claim,
    by_number: dict[int, Claim],
    terms_by_claim: dict[int, list[object]],
) -> set[str]:
    terms: set[str] = set()
    for referenced in claim.referenced_claims:
        if referenced not in by_number:
            continue
        terms.update(occurrence.term for occurrence in terms_by_claim.get(referenced, []))
    return terms


def check_term_variations(claims: list[Claim], tree: object | None) -> list[Diagnostic]:
    term_sources = _document_term_sources(claims, tree)
    terms = sorted(term_sources)
    diagnostics: list[Diagnostic] = []

    for index, first in enumerate(terms):
        for second in terms[index + 1 :]:
            suffix = _common_suffix(first, second)
            if (
                len(suffix) >= 2
                and first[0] != second[0]
                and _unmatched_prefix_lengths(first, second, suffix) == (1, 1)
            ):
                diagnostics.append(
                    Diagnostic(
                        rule_id="TERM_VARIATION",
                        severity="warning",
                        message=(
                            f"語句 {first} と {second} は、末尾「{suffix}」が一致していますが"
                            "先頭が異なります。"
                        ),
                        location=DiagnosticLocation(
                            source_type="document", section_type="terms"
                        ),
                        suggestion="語句の表記揺れではないか確認してください。",
                    )
                )

            prefix = _common_prefix(first, second)
            if (
                len(prefix) >= 2
                and first[-1] != second[-1]
                and _unmatched_suffix_lengths(first, second, prefix) == (1, 1)
            ):
                diagnostics.append(
                    Diagnostic(
                        rule_id="TERM_VARIATION",
                        severity="warning",
                        message=(
                            f"語句 {first} と {second} は、先頭「{prefix}」が一致していますが"
                            "末尾が異なります。"
                        ),
                        location=DiagnosticLocation(
                            source_type="document", section_type="terms"
                        ),
                        suggestion="語句の表記揺れではないか確認してください。",
                    )
                )

    return diagnostics


def _document_term_sources(claims: list[Claim], tree: object | None) -> dict[str, str]:
    term_sources: dict[str, str] = {}
    for claim in claims:
        for term in extract_claim_terms(claim.text):
            if len(term) >= 3:
                term_sources.setdefault(term, f"請求項{claim.number}")
    for item in extract_document_terms_with_signs(tree):
        if len(item.term) >= 3:
            term_sources.setdefault(item.term, item.source or "不明")
    return term_sources


def _unmatched_prefix_lengths(first: str, second: str, suffix: str) -> tuple[int, int]:
    return len(first) - len(suffix), len(second) - len(suffix)


def _unmatched_suffix_lengths(first: str, second: str, prefix: str) -> tuple[int, int]:
    return len(first) - len(prefix), len(second) - len(prefix)


def _common_prefix(first: str, second: str) -> str:
    index = 0
    max_length = min(len(first), len(second))
    while index < max_length and first[index] == second[index]:
        index += 1
    return first[:index]


def _common_suffix(first: str, second: str) -> str:
    index = 0
    max_length = min(len(first), len(second))
    while index < max_length and first[-index - 1] == second[-index - 1]:
        index += 1
    return first[len(first) - index :] if index else ""


def check_term_sign_conflicts(tree: object | None) -> list[Diagnostic]:
    terms_with_signs = extract_document_terms_with_signs(tree)
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_check_same_term_different_signs(terms_with_signs))
    diagnostics.extend(_check_same_sign_different_terms(terms_with_signs))
    return diagnostics


def _check_same_term_different_signs(terms_with_signs: list[object]) -> list[Diagnostic]:
    by_term: dict[str, dict[str, set[str]]] = {}

    for item in terms_with_signs:
        sources_by_sign = by_term.setdefault(item.term, {})
        sources = sources_by_sign.setdefault(item.sign, set())
        sources.add(item.source or "不明")

    diagnostics: list[Diagnostic] = []
    for term, sources_by_sign in sorted(by_term.items()):
        if len(sources_by_sign) < 2:
            continue

        sign_locations = _format_grouped_locations(sources_by_sign)
        diagnostics.append(
            Diagnostic(
                rule_id="TERM_SIGN_CONFLICT",
                severity="warning",
                message=(
                    f"符号付語句 {term} は、複数の符号で記載されています"
                    f"（{sign_locations}）。"
                ),
                location=DiagnosticLocation(
                    source_type="document", section_type="terms_with_signs"
                ),
                suggestion="同じ語句に対応する符号が統一されているか確認してください。",
            )
        )

    return diagnostics


def _check_same_sign_different_terms(terms_with_signs: list[object]) -> list[Diagnostic]:
    by_sign: dict[str, dict[str, set[str]]] = {}

    for item in terms_with_signs:
        sources_by_term = by_sign.setdefault(item.sign, {})
        sources = sources_by_term.setdefault(item.term, set())
        sources.add(item.source or "不明")

    diagnostics: list[Diagnostic] = []
    for sign, sources_by_term in sorted(by_sign.items()):
        if len(sources_by_term) < 2:
            continue

        term_locations = _format_grouped_locations(sources_by_term)
        diagnostics.append(
            Diagnostic(
                rule_id="SIGN_TERM_CONFLICT",
                severity="warning",
                message=(
                    f"符号 {sign} は、複数の語句で記載されています"
                    f"（{term_locations}）。"
                ),
                location=DiagnosticLocation(
                    source_type="document", section_type="terms_with_signs"
                ),
                suggestion="同じ符号に対応する語句が統一されているか確認してください。",
            )
        )

    return diagnostics


def _format_grouped_locations(grouped_locations: dict[str, set[str]]) -> str:
    return "、".join(
        f"{label}: {', '.join(sorted(sources))}"
        for label, sources in sorted(grouped_locations.items())
    )


def check_claim_terms_in_embodiments(
    claims: list[Claim], tree: object | None
) -> list[Diagnostic]:
    return _check_claim_terms_in_section(
        claims=claims,
        tree=tree,
        section_kind="description_of_embodiments",
        rule_id="CLAIM_TERM_IN_EMBODIMENTS",
        section_label="実施形態",
    )


def check_claim_terms_in_tech_solution(
    claims: list[Claim], tree: object | None
) -> list[Diagnostic]:
    return _check_claim_terms_in_section(
        claims=claims,
        tree=tree,
        section_kind="tech_solution",
        rule_id="CLAIM_TERM_IN_TECH_SOLUTION",
        section_label="解決手段",
    )


def _check_claim_terms_in_section(
    claims: list[Claim],
    tree: object | None,
    section_kind: str,
    rule_id: str,
    section_label: str,
) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    section_text = _section_paragraph_text(tree, section_kind)
    if not section_text:
        return []

    normalized_section_text = normalize_term_text(section_text)
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        for term in extract_claim_terms(claim.text):
            if normalize_term_text(term) in normalized_section_text:
                continue
            diagnostics.append(
                Diagnostic(
                    rule_id=rule_id,
                    severity="warning",
                    message=f"請求項の語句 {term}は、{section_label}に記載されていません",
                    location=_claim_location(claim),
                    suggestion=f"請求項の語句が{section_label}に記載されているか確認してください。",
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


def _paragraph_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for match in re.finditer(r"[。．]", text):
        sentence = text[start : match.end()].strip()
        if sentence:
            sentences.append(sentence)
        start = match.end()

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)

    return sentences


def check_claim_numbering(claims: list[Claim]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not claims:
        return [
            Diagnostic(
                rule_id="CLAIM_NUMBERING",
                severity="warning",
                message="請求項が見つかりません。",
                location=DiagnosticLocation(source_type="document", section_type="claims"),
                suggestion="【請求項1】の形式で請求項が記載されているか確認してください。",
            )
        ]

    counts = Counter(claim.number for claim in claims)
    by_number = {claim.number: claim for claim in claims}
    for number, count in sorted(counts.items()):
        if count > 1:
            claim = by_number[number]
            diagnostics.append(
                Diagnostic(
                    rule_id="CLAIM_NUMBERING",
                    severity="error",
                    message=f"請求項{number}が重複しています。",
                    location=_claim_location(claim),
                    suggestion="請求項番号を一意にしてください。",
                )
            )

    positive_numbers = [claim.number for claim in claims if claim.number > 0]
    if positive_numbers:
        for expected in range(1, max(positive_numbers) + 1):
            if expected not in counts:
                next_claim = next((claim for claim in claims if claim.number > expected), None)
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_NUMBERING",
                        severity="error",
                        message=f"請求項{expected}が欠落しています。",
                        location=_claim_location(next_claim) if next_claim else DiagnosticLocation(source_type="document", section_type="claims"),
                        suggestion="請求項番号が連続しているか確認してください。",
                    )
                )

    for claim in claims:
        if claim.number <= 0:
            diagnostics.append(
                Diagnostic(
                    rule_id="CLAIM_NUMBERING",
                    severity="error",
                    message=f"請求項番号{claim.number}は使用できません。",
                    location=_claim_location(claim),
                    suggestion="請求項番号は1以上の整数にしてください。",
                )
            )

    return diagnostics


def check_claim_dependency(claims: list[Claim]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    existing = {claim.number for claim in claims}

    for claim in claims:
        for referenced in claim.referenced_claims:
            if referenced not in existing:
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_DEPENDENCY",
                        severity="error",
                        message=f"請求項{claim.number}が存在しない請求項{referenced}を引用しています。",
                        location=_claim_location(claim),
                        suggestion="引用先の請求項番号を確認してください。",
                    )
                )
            elif referenced == claim.number:
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_DEPENDENCY",
                        severity="error",
                        message=f"請求項{claim.number}が自己引用しています。",
                        location=_claim_location(claim),
                        suggestion="自己引用にならないよう引用関係を修正してください。",
                    )
                )
            elif referenced > claim.number:
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_DEPENDENCY",
                        severity="error",
                        message=f"請求項{claim.number}が後続の請求項{referenced}を引用しています。",
                        location=_claim_location(claim),
                        suggestion="先行する請求項のみを引用してください。",
                    )
                )

    return diagnostics


def check_multi_multi_claim(claims: list[Claim]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        if claim.is_multi_multi:
            diagnostics.append(
                Diagnostic(
                    rule_id="MULTI_MULTI_CLAIM",
                    severity="warning",
                    message=f"請求項{claim.number}がマルチマルチクレームとして検出されました。",
                    location=_claim_location(claim),
                    suggestion="マルチマルチクレームに該当しないか確認してください。",
                )
            )
        elif claim.references_multi_multi:
            diagnostics.append(
                Diagnostic(
                    rule_id="MULTI_MULTI_CLAIM",
                    severity="warning",
                    message=f"請求項{claim.number}がマルチマルチクレームを引用しています。",
                    location=_claim_location(claim),
                    suggestion="マルチマルチクレームを引用する請求項に該当しないか確認してください。",
                )
            )

    return diagnostics


def _section_paragraph_text(tree: object, section_kind: str) -> str:
    paragraphs = []
    for section in tree.find_all(kind=section_kind):
        paragraphs.extend(section.find_all(kind="paragraph"))
    return "\n".join(_node_text(paragraph) for paragraph in paragraphs)


def _node_text(node: object) -> str:
    chunks = [getattr(node, "text", "")]
    for child in getattr(node, "children", []):
        chunks.append(_node_text(child))
    return "\n".join(chunk for chunk in chunks if chunk)


def _paragraph_location(paragraph: object | None) -> DiagnosticLocation:
    if paragraph is None:
        return DiagnosticLocation(source_type="document", section_type="paragraphs")

    tag_name = getattr(paragraph, "tag_name", None)
    search_text = f"【{tag_name}】" if tag_name else None
    return DiagnosticLocation(
        source_type="document",
        section_type="paragraphs",
        block_index=getattr(paragraph, "block_index", None),
        search_text=search_text,
    )


def _claim_location(claim: Claim | None) -> DiagnosticLocation:
    if claim is None:
        return DiagnosticLocation(source_type="document", section_type="claims")
    return DiagnosticLocation(
        source_type="document",
        section_type="claims",
        claim_number=claim.number,
        block_index=claim.block_index,
        search_text=claim.search_text,
    )
