from __future__ import annotations

import re

from patent_checker_common import DiagnosticLocation

from ..parser import Claim

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


def _paragraph_label(paragraph: object) -> str:
    number = getattr(paragraph, "number", None)
    if isinstance(number, int):
        return f"段落【{number:04d}】"
    tag_name = getattr(paragraph, "tag_name", None)
    if tag_name:
        return f"段落【{tag_name}】"
    return "段落"


def _dedupe_strings_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result
