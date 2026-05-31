from __future__ import annotations

import json
import re
from collections.abc import Sequence
from html import escape
from pathlib import Path

_FULLWIDTH_ASCII = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "０１２３４５６７８９",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
)
_SIGN_TRANSLATION = str.maketrans(
    {
        "－": "-",
        "ー": "-",
        "―": "-",
        "‐": "-",
        "’": "'",
        "＇": "'",
    }
)
_TEMPLATE_PATH = Path(__file__).with_name("templates") / "reference_signs.html"


def render_reference_sign_list(terms_with_signs: Sequence[object] | None) -> str:
    if terms_with_signs is None:
        return ""

    entries = reference_sign_entries(terms_with_signs)
    rows = []
    for entry in entries:
        rows.append(
            "<tr>"
            f"<td>{escape(entry['sign'])}</td>"
            f"<td>{escape(entry['term'])}</td>"
            f"<td>{escape(entry['source'])}</td>"
            "</tr>"
        )

    if not rows:
        rows.append('<tr><td colspan="3">No signed terms.</td></tr>')

    data = json.dumps(entries, ensure_ascii=False).replace("</", "<\\/")
    return _load_template().replace("{{REFERENCE_SIGN_ROWS}}", "".join(rows)).replace(
        "{{REFERENCE_SIGN_DATA}}", data
    )


def reference_sign_entries(terms_with_signs: Sequence[object]) -> list[dict[str, str]]:
    entries_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for item in terms_with_signs:
        sign = str(getattr(item, "sign", "") or "").strip()
        term = str(getattr(item, "term", "") or "").strip()
        source = str(getattr(item, "source", "") or "").strip()
        if not sign or not term:
            continue
        key = (_normalize_sign_for_sort(sign), term)
        if key not in entries_by_key:
            entries_by_key[key] = {"sign": sign, "term": term, "source": source}
        elif source and source not in entries_by_key[key]["source"].split("、"):
            entries_by_key[key]["source"] = "、".join(
                value for value in [entries_by_key[key]["source"], source] if value
            )

    return sorted(
        entries_by_key.values(),
        key=lambda entry: _sign_sort_key(entry["sign"]),
    )


def _load_template() -> str:
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def _normalize_sign_for_sort(sign: str) -> str:
    return (
        sign.translate(_SIGN_TRANSLATION)
        .translate(_FULLWIDTH_ASCII)
        .replace(" ", "")
        .replace("　", "")
        .upper()
    )


def _sign_sort_key(sign: str) -> tuple[object, ...]:
    normalized = _normalize_sign_for_sort(sign)
    match = re.match(r"^([A-Z]+)?(?:-)?(\d+)?(.*)$", normalized)
    if match is None:
        return (3, normalized)

    letters = match.group(1) or ""
    number = int(match.group(2)) if match.group(2) else None
    rest = match.group(3) or ""

    if letters and number is None:
        return (0, letters, rest)
    if letters and number is not None:
        return (0, letters, 0, number, rest)
    if number is not None:
        return (1, number, _sign_rest_rank(rest), rest)
    return (2, normalized)


def _sign_rest_rank(rest: str) -> int:
    if not rest:
        return 0
    if re.match(r"^[A-ZＡ-Ｚａ-ｚぁ-んァ-ヶ]", rest):
        return 1
    if rest.startswith("-"):
        return 2
    return 3
