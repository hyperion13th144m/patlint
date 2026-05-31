from __future__ import annotations

import re

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
REFERENCE_TERM_PREFIXES = ("前記", "当該", "該")
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
