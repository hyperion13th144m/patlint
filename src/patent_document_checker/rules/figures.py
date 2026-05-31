from __future__ import annotations

import re
import unicodedata

from patent_checker_common import Diagnostic, DiagnosticLocation

from .common import _node_text, _paragraph_location


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
