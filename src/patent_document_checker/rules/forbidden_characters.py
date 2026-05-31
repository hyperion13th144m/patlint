from __future__ import annotations

import unicodedata

from patent_checker_common import Diagnostic, DiagnosticLocation

from ..parser import RawBlock

# JPO's JIS X 0208 table displays these glyphs, while Python's strict
# shift_jis codec accepts their alternate Unicode mappings instead.
JPO_ALLOWED_SHIFT_JIS_VARIANTS = frozenset({"～", "－", "∥", "￢", "￠", "￡", "￤"})


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
