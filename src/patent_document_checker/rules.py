from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
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
WORD_RULE_CATEGORIES = frozenset(
    {
        "claims_ng",
        "spec_pl",
        "spec_antimonopoly",
        "spec_trademark",
        "typo_words",
        "typo_regex",
    }
)
CLAIM_WORD_RULE_CATEGORIES = frozenset({"claims_ng", "typo_words", "typo_regex"})
SPEC_WORD_RULE_CATEGORIES = frozenset(
    {"spec_pl", "spec_antimonopoly", "spec_trademark", "typo_words", "typo_regex"}
)


@dataclass(frozen=True, slots=True)
class WordRulePattern:
    category: str
    pattern: str
    label: str
    is_regex: bool = False


def run_document_rules(document: PatentDocumentIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_forbidden_characters(document.raw_blocks))
    diagnostics.extend(check_recommended_wording(document))
    diagnostics.extend(check_paragraph_numbering(document.tree))
    diagnostics.extend(check_paragraph_end_punctuation(document.tree))
    diagnostics.extend(check_claim_numbering(document.claims))
    diagnostics.extend(check_claim_dependency(document.claims))
    diagnostics.extend(check_multi_multi_claim(document.claims))
    diagnostics.extend(check_missing_claim_term_reference_prefix(document.claims))
    diagnostics.extend(check_term_variations(document.claims, document.tree))
    diagnostics.extend(check_term_sign_conflicts(document.tree))
    diagnostics.extend(check_claim_terms_in_embodiments(document.claims, document.tree))
    diagnostics.extend(check_claim_terms_in_tech_solution(document.claims, document.tree))
    diagnostics.extend(check_long_embodiment_sentences(document.tree))
    diagnostics.extend(check_missing_subject_in_embodiment_sentences(document.tree))
    diagnostics.extend(check_abstract_length(document.tree))
    diagnostics.extend(check_invention_title_matches_independent_claims(document.claims, document.tree))
    diagnostics.extend(check_dependent_claim_invention_name_matches_references(document.claims))
    diagnostics.extend(check_figure_references(document.tree))
    return diagnostics


def check_recommended_wording(document: PatentDocumentIR) -> list[Diagnostic]:
    patterns = _load_word_rule_patterns()
    if not patterns:
        return []

    diagnostics: list[Diagnostic] = []
    for claim in document.claims:
        diagnostics.extend(
            _match_word_rule_patterns(
                text=claim.text,
                patterns=(
                    pattern
                    for pattern in patterns
                    if pattern.category in CLAIM_WORD_RULE_CATEGORIES
                ),
                location=_claim_location(claim),
            )
        )

    if document.tree is not None and hasattr(document.tree, "find_all"):
        for paragraph in document.tree.find_all(kind="paragraph"):
            diagnostics.extend(
                _match_word_rule_patterns(
                    text=_node_text(paragraph),
                    patterns=(
                        pattern
                        for pattern in patterns
                        if pattern.category in SPEC_WORD_RULE_CATEGORIES
                    ),
                    location=_paragraph_location(paragraph),
                )
            )

    return diagnostics


def _match_word_rule_patterns(
    text: str,
    patterns: object,
    location: DiagnosticLocation,
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[str, str, str, int]] = set()
    for pattern in patterns:
        regex = pattern.pattern if pattern.is_regex else re.escape(pattern.pattern)
        try:
            matches = list(re.finditer(regex, text))
        except re.error:
            continue
        for match in matches:
            matched_text = match.group(0)
            key = (pattern.category, pattern.pattern, matched_text, match.start())
            if key in seen:
                continue
            seen.add(key)
            diagnostics.append(
                Diagnostic(
                    rule_id=f"RECOMMENDED_WORDING_{pattern.category.upper()}",
                    severity="warning",
                    message=(
                        f"推奨されない語句・表現 {matched_text} が含まれています"
                        f"（カテゴリ: {pattern.category}、{pattern.label}）。"
                    ),
                    location=location,
                    suggestion="語句・表現を見直してください。",
                )
            )
    return diagnostics


@lru_cache(maxsize=1)
def _load_word_rule_patterns() -> tuple[WordRulePattern, ...]:
    words_dir = _find_words_dir()
    if words_dir is None:
        return ()

    patterns: list[WordRulePattern] = []
    for filename in ("default.json", "custom.json"):
        patterns.extend(_load_word_json(words_dir / filename))
    patterns.extend(_load_extra_words(words_dir / "extra.txt"))
    patterns.extend(_load_python_patterns(words_dir / "patterns.py"))
    return tuple(_dedupe_word_rule_patterns(patterns))


def _find_words_dir() -> Path | None:
    search_roots = (
        Path.cwd(),
        *Path.cwd().parents,
        Path(__file__).resolve().parent,
        *Path(__file__).resolve().parents,
    )
    for parent in search_roots:
        candidate = parent / "words"
        if candidate.is_dir():
            return candidate
    return None


def _load_word_json(path: Path) -> list[WordRulePattern]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    patterns: list[WordRulePattern] = []
    for category, words in data.items():
        if category not in WORD_RULE_CATEGORIES or not isinstance(words, list):
            continue
        for word in words:
            if isinstance(word, str) and word:
                patterns.append(WordRulePattern(category, word, word))
    return patterns


def _load_extra_words(path: Path) -> list[WordRulePattern]:
    if not path.exists():
        return []
    patterns: list[WordRulePattern] = []
    category: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            match = re.search(r"カテゴリ\s*:\s*([A-Za-z0-9_]+)", line)
            if match and match.group(1) in WORD_RULE_CATEGORIES:
                category = match.group(1)
            continue
        if category is not None:
            patterns.append(WordRulePattern(category, line, line))
    return patterns


def _load_python_patterns(path: Path) -> list[WordRulePattern]:
    if not path.exists():
        return []
    spec = importlib.util.spec_from_file_location("patent_checker_word_patterns", path)
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    patterns: list[WordRulePattern] = []
    for item in getattr(module, "PATTERNS", []):
        if not isinstance(item, tuple) or len(item) != 3:
            continue
        category, pattern, label = item
        if category in WORD_RULE_CATEGORIES and isinstance(pattern, str) and isinstance(label, str):
            patterns.append(WordRulePattern(category, pattern, label, is_regex=True))
    return patterns


def _dedupe_word_rule_patterns(patterns: list[WordRulePattern]) -> list[WordRulePattern]:
    seen: set[WordRulePattern] = set()
    result: list[WordRulePattern] = []
    for pattern in patterns:
        if pattern in seen:
            continue
        seen.add(pattern)
        result.append(pattern)
    return result


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


def check_figure_references(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    listed_figures = _listed_figure_numbers(tree)
    mentioned_figures = _mentioned_figure_numbers(tree)
    diagnostics: list[Diagnostic] = []

    for number in sorted(set(listed_figures) - set(mentioned_figures)):
        diagnostics.append(
            Diagnostic(
                rule_id="FIGURE_REFERENCE",
                severity="warning",
                message=f"図{number}は明細書で言及されていません。",
                location=DiagnosticLocation(
                    source_type="document",
                    section_type="description_of_drawings",
                    search_text=f"【図{number}】",
                ),
                suggestion="図面の簡単な説明に記載された図が本文中で言及されているか確認してください。",
            )
        )

    for number in sorted(set(mentioned_figures) - set(listed_figures)):
        paragraph = mentioned_figures[number]
        diagnostics.append(
            Diagnostic(
                rule_id="FIGURE_REFERENCE",
                severity="warning",
                message=f"図{number}は明細書で言及されていますが、図面の簡単な説明に記載されていません。",
                location=_paragraph_location(paragraph),
                suggestion="本文中で言及された図を図面の簡単な説明にも記載してください。",
            )
        )

    return diagnostics


def _listed_figure_numbers(tree: object) -> set[int]:
    numbers: set[int] = set()
    for drawings in tree.find_all(kind="description_of_drawings"):
        for figure in drawings.find_all(kind="figure"):
            number = getattr(figure, "number", None)
            if isinstance(number, int):
                numbers.add(number)
    return numbers


def _mentioned_figure_numbers(tree: object) -> dict[int, object]:
    mentioned: dict[int, object] = {}
    for paragraph in _paragraphs_outside_kind(tree, excluded_kind="description_of_drawings"):
        for number in _extract_figure_numbers(_node_text(paragraph)):
            mentioned.setdefault(number, paragraph)
    return mentioned


def _paragraphs_outside_kind(node: object, excluded_kind: str, excluded: bool = False) -> list[object]:
    node_kind = getattr(node, "kind", None)
    next_excluded = excluded or node_kind == excluded_kind
    paragraphs = []
    if node_kind == "paragraph" and not next_excluded:
        paragraphs.append(node)
    for child in getattr(node, "children", []):
        paragraphs.extend(_paragraphs_outside_kind(child, excluded_kind, next_excluded))
    return paragraphs


def _extract_figure_numbers(text: str) -> set[int]:
    normalized = unicodedata.normalize("NFKC", text)
    numbers: set[int] = set()
    for match in re.finditer(r"図\s*([0-9]+)(?:\s*(?:から|～|〜|－|-)\s*(?:図)?\s*([0-9]+))?", normalized):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        step = 1 if end >= start else -1
        numbers.update(range(start, end + step, step))
    return numbers


def check_invention_title_matches_independent_claims(
    claims: list[Claim], tree: object | None
) -> list[Diagnostic]:
    title_terms = _invention_title_terms(tree)
    if not title_terms:
        return []

    claim_terms = _independent_claim_terminal_terms(claims)
    if title_terms == claim_terms:
        return []

    return [
        Diagnostic(
            rule_id="INVENTION_TITLE_CLAIM_MISMATCH",
            severity="error",
            message=(
                "発明の名称と独立請求項の末尾語句が一致していません"
                f"（発明の名称: {', '.join(title_terms)} / "
                f"独立請求項: {', '.join(claim_terms) if claim_terms else 'なし'}）。"
            ),
            location=DiagnosticLocation(
                source_type="document", section_type="invention_title"
            ),
            suggestion="発明の名称と独立請求項に記載された発明カテゴリが一致しているか確認してください。",
        )
    ]


def _invention_title_terms(tree: object | None) -> list[str]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    terms: list[str] = []
    for title in tree.find_all(kind="invention_title"):
        for term in re.split(r"、|，|及び|並びに|および|ならびに", _node_text(title)):
            stripped = term.strip()
            if stripped:
                terms.append(stripped)

    return _dedupe_strings_preserving_order(terms)


def _independent_claim_terminal_terms(claims: list[Claim]) -> list[str]:
    terms = []
    for claim in claims:
        if claim.referenced_claims:
            continue
        term = _claim_terminal_term(claim.text)
        if term:
            terms.append(term)
    return _dedupe_strings_preserving_order(terms)


def _claim_terminal_term(text: str) -> str:
    normalized = re.sub(r"\s+", "", text).strip("。．")
    if not normalized:
        return ""

    marker = "ことを特徴とする"
    if marker in normalized:
        normalized = normalized.rsplit(marker, maxsplit=1)[-1]

    normalized = re.sub(
        r"^請求項[0-9０-９]+(?:(?:又は|または|及び|および|から|乃至|ないし|～|－|-|、|，|,)(?:請求項)?[0-9０-９]+)*に記載の",
        "",
        normalized,
    )
    return normalized.strip("、，。．")


def _dedupe_strings_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


def check_dependent_claim_invention_name_matches_references(
    claims: list[Claim],
) -> list[Diagnostic]:
    by_number = {claim.number: claim for claim in claims}
    terminal_terms = {
        claim.number: _claim_terminal_term(claim.text) for claim in claims
    }
    diagnostics: list[Diagnostic] = []

    for claim in claims:
        if not claim.referenced_claims:
            continue

        claim_term = terminal_terms.get(claim.number, "")
        if not claim_term:
            continue

        mismatches = []
        for referenced in claim.referenced_claims:
            referenced_claim = by_number.get(referenced)
            if referenced_claim is None:
                continue
            referenced_term = terminal_terms.get(referenced, "")
            if referenced_term and referenced_term != claim_term:
                mismatches.append(f"請求項{referenced}: {referenced_term}")

        if not mismatches:
            continue

        diagnostics.append(
            Diagnostic(
                rule_id="DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH",
                severity="error",
                message=(
                    f"請求項{claim.number}の発明の名称 {claim_term} は、"
                    "参照元請求項の発明の名称と一致していません"
                    f"（参照元: {', '.join(mismatches)}）。"
                ),
                location=_claim_location(claim),
                suggestion="従属請求項の末尾語句と参照元請求項の末尾語句が一致しているか確認してください。",
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


def _paragraph_label(paragraph: object) -> str:
    number = getattr(paragraph, "number", None)
    if isinstance(number, int):
        return f"段落【{number:04d}】"
    tag_name = getattr(paragraph, "tag_name", None)
    if tag_name:
        return f"段落【{tag_name}】"
    return "段落"


def check_abstract_length(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    diagnostics: list[Diagnostic] = []
    for abstract in tree.find_all(kind="abstract_tag"):
        text = _node_text(abstract)
        length = len(text)
        if length <= 400:
            continue
        diagnostics.append(
            Diagnostic(
                rule_id="ABSTRACT_LENGTH",
                severity="error",
                message=f"要約書の文字数が400文字を超えています（{length}文字）。",
                location=DiagnosticLocation(
                    source_type="document",
                    section_type="abstract",
                    block_index=getattr(abstract, "block_index", None),
                    search_text="【要約】",
                ),
                suggestion="要約書を400文字以内にしてください。",
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
