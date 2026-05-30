from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ][0-9A-Za-z０-９Ａ-Ｚａ-ｚ]{2,}")

PREFIXED_TERM_PATTERN = re.compile(
    r"(?:前記|上記|下記|当該|該|各|本)"
    r"[0-9A-Za-zＡ-Ｚａ-ｚァ-ヴー一-龥々]{2,30}(?=[はがをにでとのや、。\n]|$)"
)

ORDINAL_TERM_PATTERN = re.compile(
    r"第[0-9]+の?[0-9A-Za-zァ-ヴー一-龥々ー]{2,24}(?=[はがをにでとのや、。\n]|$)"
)

KATAKANA_TECHNICAL_PATTERN = re.compile(
    r"(?:"
    r"(?<=[をがはのにでも])[ァ-ヴー]{4,20}(?=[をがはのにでもとや、。])"
    r"|"
    r"[一-龥々０-９]{1,6}[ァ-ヴー]{3,16}"
    r"|"
    r"[ァ-ヴー]{3,16}[一-龥々]{1,6}"
    r")"
)

KATAKANA_COMPOUND_PATTERN = re.compile(
    r"(?:[A-Za-zＡ-Ｚａ-ｚ]+[ァ-ヴー]{2,}|[ァ-ヴー]{2,}[A-Za-z0-9Ａ-Ｚａ-ｚ]+)"
    r"|(?:[ァ-ヴー]{4,20}(?:化|型|式|用|系|基|層|膜|板|線|波|体|剤|液|素|環|類)(?:[ァ-ヴー]{4,20})?)"
)

IUPAC_PATTERN = re.compile(
    r"[0-9０-９ａ-ｚＡ-Ｚ]+[－\-][ァ-ヴーA-Za-z０-９Ａ-Ｚａ-ｚ]"
    r"[ァ-ヴーA-Za-z０-９Ａ-Ｚａ-ｚ0-9０-９－\-]{2,22}"
)

KANJI_COMPOUND_PATTERN = re.compile(
    r"(?<![一-龥々])[一-龥々]{2,16}(?=[はがをにでとのや、。\n]|$)"
)

TERM_PATTERNS = (
    PREFIXED_TERM_PATTERN,
    ORDINAL_TERM_PATTERN,
    IUPAC_PATTERN,
    KATAKANA_TECHNICAL_PATTERN,
    KATAKANA_COMPOUND_PATTERN,
    ASCII_TOKEN_PATTERN,
    KANJI_COMPOUND_PATTERN,
)

DEFAULT_DICTIONARY_STEMS = frozenset(
    {
        "ねじ",
        "送り出し",
        "位置決め",
        "取り付け",
        "歯付き",
        "ばね",
        "継ぎ手",
        "はずみ車",
        "つるまきバネ",
        "うずまきバネ",
        "溝付き",
        "割りピン",
        "植え込み",
        "絞り",
        "振り子",
        "吊り上げ",
        "吊り下げ",
        "ろ過",
        "折れ曲がり",
        "立ち上がり",
        "立ち下がり",
        "圧縮ばね",
        "金型受け",
        "中抜き",
        "めっき層",
        "Ｘ線",
        "折り目",
        "雌ねじ孔",
        "貫通らせん転位",
        "ばね受け",
        "圧縮コイルばね",
        "軸受け",
        "切り欠き",
        "液体溜まり",
    }
)
DICTIONARY_SUFFIXES = (
    "部材",
    "部",
    "機構",
    "手段",
    "体",
    "工程",
    "ステップ",
)

STOPWORDS = frozenset(
    {
        "請求項",
        "前記",
        "上記",
        "下記",
        "当該",
        "本発明",
        "実施形態",
        "発明",
        "構成",
        "場合",
        "記載",
        "装置",
        "方法",
        "工程",
        "手段",
        "部分",
        "複数",
        "一部",
        "少なくとも",
        "いずれか",
        "特徴",
        "周囲",
        "一方",
        "他方",
        "一項",
        "",
    }
)

TERM_PREFIXES = ("前記", "上記", "下記", "当該", "該", "各", "本")
DASH_CHARS = "‐‑‒–—―−－～〜~"
DASH_TRANSLATION = str.maketrans({char: "-" for char in DASH_CHARS})
Candidate = tuple[int, int, int, str]

SIGN_BODY = r"[0-9A-Za-z０-９Ａ-Ｚａ-ｚ]+(?:[-][0-9A-Za-z０-９Ａ-Ｚａ-ｚ]+)*(?:['’])?"
SIGNED_TERM_PATTERN = re.compile(
    r"(?P<term>"
    r"第[0-9]+の?[ァ-ヴー一-龥々ー]{2,24}"
    r"|[一-龥々０-９]{1,6}[ァ-ヴー]{3,16}[一-龥々]{0,6}"
    r"|[ァ-ヴー]{3,16}[一-龥々]{1,10}"
    r"|[ァ-ヴー]{2,16}"
    r"|[A-Za-zＡ-Ｚａ-ｚ]+[ァ-ヴー]{2,}"
    r"|[ァ-ヴー]{2,}[A-Za-z0-9Ａ-Ｚａ-ｚ]+"
    r"|[一-龥々]{2,16}"
    r")"
    rf"(?P<sign>{SIGN_BODY})(?=[はがをにでとのや、。\n]|$)"
)


@dataclass(frozen=True, slots=True)
class TermWithSign:
    whole_string: str
    term: str
    sign: str
    source: str | None = None


def normalize_term_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(DASH_TRANSLATION).replace("’", "'")
    return re.sub(r"\s+", "", normalized)


def extract_terms_with_signs(
    text: str, source: str | None = None
) -> list[TermWithSign]:
    normalized = normalize_term_text(text)
    results: list[TermWithSign] = []

    for match in SIGNED_TERM_PATTERN.finditer(normalized):
        term = _prepare_term(match.group("term"))
        sign = normalize_term_text(match.group("sign"))
        if _is_noise_term(term):
            continue
        results.append(
            TermWithSign(
                whole_string=f"{term}{sign}",
                term=term,
                sign=sign,
                source=source,
            )
        )

    return results


def extract_document_terms_with_signs(tree: object | None) -> list[TermWithSign]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    results: list[TermWithSign] = []
    for text, source in _target_texts_for_terms_with_signs(tree):
        results.extend(extract_terms_with_signs(text, source=source))
    return results


def extract_claim_terms(
    text: str, dictionary_terms: Iterable[str] | None = DEFAULT_DICTIONARY_STEMS
) -> list[str]:
    normalized = normalize_term_text(text)
    return _dedupe_preserving_order(
        candidate[3]
        for candidate in _term_candidates(normalized, dictionary_terms=dictionary_terms)
    )


def extract_term_occurrences(claims: Iterable[object], tree: object | None) -> dict[str, list[str]]:
    occurrences: dict[str, list[str]] = {}

    for claim in claims:
        location = f"請求項{getattr(claim, 'number')}"
        for term in extract_claim_terms(getattr(claim, "text")):
            _add_occurrence(occurrences, term, location)

    for item in extract_document_terms_with_signs(tree):
        _add_occurrence(occurrences, item.whole_string, item.source or "不明")

    return dict(sorted(occurrences.items()))


def extract_claim_terms_by_number(
    claims: Iterable[object],
    dictionary_terms: Iterable[str] | None = DEFAULT_DICTIONARY_STEMS,
) -> dict[int, list[str]]:
    terms_by_number: dict[int, list[str]] = {}
    for claim in claims:
        number = getattr(claim, "number")
        text = getattr(claim, "text")
        terms_by_number[number] = extract_claim_terms(text, dictionary_terms)
    return terms_by_number


def _term_candidates(
    normalized_text: str,
    dictionary_terms: Iterable[str] | None = DEFAULT_DICTIONARY_STEMS,
) -> list[Candidate]:
    candidates: list[Candidate] = []

    for priority, pattern in enumerate(TERM_PATTERNS, start=1):
        for match in pattern.finditer(normalized_text):
            term = _prepare_term(match.group(0))
            if _is_noise_term(term):
                continue
            candidates.append((match.start(), match.end(), priority, term))

    if dictionary_terms is not None:
        for raw_stem in dictionary_terms:
            stem = _prepare_term(raw_stem)
            if _is_noise_term(stem):
                continue
            pattern = _dictionary_stem_pattern(stem)
            for match in pattern.finditer(normalized_text):
                term = _prepare_term(match.group(0))
                if _is_noise_term(term):
                    continue
                candidates.append((match.start(), match.end(), 0, term))

    return _select_non_overlapping(candidates)


def _add_occurrence(occurrences: dict[str, list[str]], term: str, location: str) -> None:
    locations = occurrences.setdefault(term, [])
    if location not in locations:
        locations.append(location)


def _dictionary_stem_pattern(stem: str) -> re.Pattern[str]:
    suffix_pattern = "|".join(re.escape(suffix) for suffix in DICTIONARY_SUFFIXES)
    return re.compile(rf"{re.escape(stem)}(?:{suffix_pattern})")


def _target_texts_for_terms_with_signs(tree: object) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for embodiment in tree.find_all(kind="description_of_embodiments"):
        for paragraph in embodiment.find_all(kind="paragraph"):
            text = _node_text(paragraph)
            if text:
                texts.append((text, _paragraph_source(paragraph)))
    for abstract in tree.find_all(kind="abstract_tag"):
        text = _node_text(abstract)
        if text:
            texts.append((text, "要約書"))
    return texts


def _paragraph_source(paragraph: object) -> str:
    number = getattr(paragraph, "number", None)
    if isinstance(number, int):
        return f"{number:04d}"
    tag_name = getattr(paragraph, "tag_name", None)
    return str(tag_name) if tag_name else ""


def _node_text(node: object) -> str:
    chunks = [getattr(node, "text", "")]
    for child in getattr(node, "children", []):
        chunks.append(_node_text(child))
    return "\n".join(chunk for chunk in chunks if chunk)


def _prepare_term(value: str) -> str:
    term = normalize_term_text(value).strip("、。，．・:：;；()（）[]［］{}｛｝")
    changed = True
    while changed:
        changed = False
        for prefix in TERM_PREFIXES:
            if term.startswith(prefix) and len(term) > len(prefix) + 1:
                term = term[len(prefix) :]
                changed = True
                break
    return term


def _is_noise_term(term: str) -> bool:
    if len(term) < 2:
        return True
    if term in STOPWORDS:
        return True
    if term.startswith("請求項"):
        return True
    if re.fullmatch(r"[0-9０-９]+", term):
        return True
    return False


def _select_non_overlapping(candidates: list[Candidate]) -> list[Candidate]:
    selected: list[Candidate] = []
    occupied: list[tuple[int, int]] = []
    for candidate in sorted(
        candidates, key=lambda item: (item[0], -(item[1] - item[0]), item[2])
    ):
        start, end, _, _ = candidate
        if any(
            start < occupied_end and end > occupied_start
            for occupied_start, occupied_end in occupied
        ):
            continue
        selected.append(candidate)
        occupied.append((start, end))
    return sorted(selected, key=lambda item: item[0])


def _dedupe_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
