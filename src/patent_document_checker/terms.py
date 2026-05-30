from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ][0-9A-Za-z０-９Ａ-Ｚａ-ｚ]{2,}")

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
    ORDINAL_TERM_PATTERN,
    IUPAC_PATTERN,
    KATAKANA_TECHNICAL_PATTERN,
    KATAKANA_COMPOUND_PATTERN,
    ASCII_TOKEN_PATTERN,
    KANJI_COMPOUND_PATTERN,
)

DEFAULT_DICTIONARY_TERMS = frozenset(
    {
        "ねじ部材",
        "送り出し機構",
    }
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


def normalize_term_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(DASH_TRANSLATION)
    return re.sub(r"\s+", "", normalized)


def extract_claim_terms(
    text: str, dictionary_terms: Iterable[str] | None = DEFAULT_DICTIONARY_TERMS
) -> list[str]:
    normalized = normalize_term_text(text)
    candidates: list[Candidate] = []

    for priority, pattern in enumerate(TERM_PATTERNS, start=1):
        for match in pattern.finditer(normalized):
            term = _prepare_term(match.group(0))
            if _is_noise_term(term):
                continue
            candidates.append((match.start(), match.end(), priority, term))

    if dictionary_terms is not None:
        for raw_term in dictionary_terms:
            term = _prepare_term(raw_term)
            if _is_noise_term(term):
                continue
            for match in re.finditer(re.escape(term), normalized):
                candidates.append((match.start(), match.end(), 0, term))

    return _dedupe_preserving_order(
        candidate[3] for candidate in _select_non_overlapping(candidates)
    )


def extract_claim_terms_by_number(
    claims: Iterable[object],
    dictionary_terms: Iterable[str] | None = DEFAULT_DICTIONARY_TERMS,
) -> dict[int, list[str]]:
    terms_by_number: dict[int, list[str]] = {}
    for claim in claims:
        number = getattr(claim, "number")
        text = getattr(claim, "text")
        terms_by_number[number] = extract_claim_terms(text, dictionary_terms)
    return terms_by_number


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
