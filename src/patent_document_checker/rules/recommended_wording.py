from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import re

from patent_checker_common import Diagnostic, DiagnosticLocation

from ..parser import PatentDocumentIR
from .common import _claim_location, _node_text, _paragraph_location

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
