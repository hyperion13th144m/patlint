from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .parser import PatentDocumentIR, RawBlock

_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?|\d+/\d+"
_NUMBER_RANGE = rf"(?:{_NUMBER})(?:\s*(?:~|-)\s*(?:{_NUMBER}))?"
_GENERIC_UNIT = r"[A-Za-zμΩÅ°℃%]+[0-9]?"

_FULLWIDTH_ASCII_TRANSLATION = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "０１２３４５６７８９",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
)
_UNIT_NORMALIZATION = str.maketrans(
    {
        "．": ".",
        "，": ",",
        "％": "%",
        "－": "-",
        "−": "-",
        "ー": "-",
        "―": "-",
        "‐": "-",
        "～": "~",
        "〜": "~",
    }
)


@dataclass(frozen=True, slots=True)
class UnitCheckResult:
    line: int
    col: int
    matched: str
    number: str
    unit: str
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class UnitCatalog:
    si_units: frozenset[str]
    non_si_units: dict[str, dict[str, str]]


def extract_unit_checks(document: PatentDocumentIR) -> list[UnitCheckResult]:
    return extract_unit_checks_from_blocks(document.raw_blocks)


def extract_unit_checks_from_blocks(blocks: list[RawBlock]) -> list[UnitCheckResult]:
    catalog = _load_unit_catalog()
    pattern = _unit_expression_pattern(catalog)
    results: list[UnitCheckResult] = []

    for block in blocks:
        normalized, index_map = _normalize_for_unit_check(block.text)
        for match in pattern.finditer(normalized):
            unit = match.group("unit")
            if not unit:
                continue
            start = index_map[match.start()]
            end = index_map[match.end() - 1] + 1
            original_match = block.text[start:end]
            level, message = _classify_unit(unit, catalog)
            results.append(
                UnitCheckResult(
                    line=block.index + 1,
                    col=start + 1,
                    matched=original_match,
                    number=match.group("number"),
                    unit=unit,
                    level=level,
                    message=message,
                )
            )

    return results


def _classify_unit(unit: str, catalog: UnitCatalog) -> tuple[str, str]:
    if unit in catalog.si_units:
        return "INFO", "SI単位またはSI併用単位です"
    if unit in catalog.non_si_units:
        entry = catalog.non_si_units[unit]
        return entry.get("level", "WARNING"), entry.get("message", "非SI単位です")
    return "INFO", "UNKNOWN：単位リストにない単位です"


def _unit_expression_pattern(catalog: UnitCatalog) -> re.Pattern[str]:
    known_units = sorted(
        set(catalog.si_units) | set(catalog.non_si_units),
        key=len,
        reverse=True,
    )
    unit_alternatives = [re.escape(unit) for unit in known_units]
    unit_alternatives.append(_GENERIC_UNIT)
    unit_pattern = "|".join(unit_alternatives)
    return re.compile(
        rf"(?<![0-9A-Za-z])(?P<number>{_NUMBER_RANGE})\s*(?P<unit>{unit_pattern})(?![0-9A-Za-z])"
    )


@lru_cache(maxsize=1)
def _load_unit_catalog() -> UnitCatalog:
    units_dir = _find_units_dir()
    if units_dir is None:
        return UnitCatalog(frozenset(), {})

    si_data = _read_json(units_dir / "si_units.json", {})
    non_si_data = _read_json(units_dir / "non_si_units.json", {})
    custom_data = _read_json(units_dir / "custom_units.json", {})

    si_units: set[str] = set()
    for key in ("base", "derived", "accepted"):
        values = si_data.get(key, [])
        if isinstance(values, list):
            si_units.update(value for value in values if isinstance(value, str))

    custom_si = custom_data.get("si", [])
    if isinstance(custom_si, list):
        si_units.update(value for value in custom_si if isinstance(value, str))

    non_si_units = {
        unit: data
        for unit, data in non_si_data.items()
        if isinstance(unit, str) and isinstance(data, dict)
    }
    custom_non_si = custom_data.get("non_si", {})
    if isinstance(custom_non_si, dict):
        non_si_units.update(
            {
                unit: data
                for unit, data in custom_non_si.items()
                if isinstance(unit, str) and isinstance(data, dict)
            }
        )

    return UnitCatalog(frozenset(si_units), non_si_units)


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _find_units_dir() -> Path | None:
    search_roots = (
        Path.cwd(),
        *Path.cwd().parents,
        Path(__file__).resolve().parent,
        *Path(__file__).resolve().parents,
    )
    for parent in search_roots:
        candidate = parent / "units"
        if candidate.is_dir():
            return candidate
    return None


def _normalize_for_unit_check(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        normalized = char.translate(_FULLWIDTH_ASCII_TRANSLATION).translate(_UNIT_NORMALIZATION)
        for normalized_char in normalized:
            chars.append(normalized_char)
            index_map.append(index)
    return "".join(chars), index_map
