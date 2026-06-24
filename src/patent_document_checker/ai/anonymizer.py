"""Simple pattern-based anonymizer for patent document text before API submission."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Patterns to detect and replace
_WORD = r"[^\s、。（）【】「」\n]{1,30}"

_PATTERNS = [
    # 株式会社・有限会社など（後置型: 「株式会社ABC」）
    (re.compile(rf"(?:株式会社|有限会社|合同会社|合資会社){_WORD}"), "company"),
    # 前置型: 「ABC株式会社」
    (re.compile(rf"{_WORD}(?:株式会社|有限会社|合同会社|合資会社|Inc\.|Ltd\.|Corp\.)"), "company"),
    # 発明者（「発明者　山田太郎」のような表記）
    (re.compile(rf"発明者[　\s]+{_WORD}"), "inventor"),
    # 出願人（「出願人　山田太郎」のような表記）
    (re.compile(rf"出願人[　\s]+{_WORD}"), "applicant"),
    # 整理番号・案件番号
    (re.compile(r"整理番号[：:\s]+[\w\-]+"), "ref_number"),
    (re.compile(r"案件番号[：:\s]+[\w\-]+"), "case_number"),
]


@dataclass
class AnonymizationMap:
    mapping: dict[str, str] = field(default_factory=dict)
    _counters: dict[str, int] = field(default_factory=dict)

    def register(self, original: str, kind: str) -> str:
        if original in self.mapping:
            return self.mapping[original]
        count = self._counters.get(kind, 0) + 1
        self._counters[kind] = count
        label = {
            "company": f"会社{_alpha(count)}",
            "inventor": f"発明者{_alpha(count)}",
            "applicant": f"出願人{_alpha(count)}",
            "ref_number": f"整理番号{count}",
            "case_number": f"案件番号{count}",
        }.get(kind, f"{kind}{count}")
        self.mapping[original] = label
        return label


def _alpha(n: int) -> str:
    """1→A, 2→B, ..."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def anonymize(text: str) -> tuple[str, AnonymizationMap]:
    """Replace identifying information with placeholders. Returns (anonymized_text, map)."""
    amap = AnonymizationMap()
    for pattern, kind in _PATTERNS:
        def replace(m: re.Match, k: str = kind) -> str:
            return amap.register(m.group(0), k)
        text = pattern.sub(replace, text)
    return text, amap
