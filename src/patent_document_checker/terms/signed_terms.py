from __future__ import annotations

from .common import is_noise_term, node_text, paragraph_source, prepare_term
from .models import TermWithSign
from .normalization import normalize_term_text
from .patterns import SIGNED_TERM_PATTERN


def extract_terms_with_signs(
    text: str, source: str | None = None
) -> list[TermWithSign]:
    normalized = normalize_term_text(text)
    results: list[TermWithSign] = []

    for match in SIGNED_TERM_PATTERN.finditer(normalized):
        term = prepare_term(match.group("term"))
        sign = normalize_term_text(match.group("sign"))
        if is_noise_term(term):
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


def _target_texts_for_terms_with_signs(tree: object) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for embodiment in tree.find_all(kind="description_of_embodiments"):
        for paragraph in embodiment.find_all(kind="paragraph"):
            text = node_text(paragraph)
            if text:
                texts.append((text, paragraph_source(paragraph)))
    for abstract in tree.find_all(kind="abstract_tag"):
        text = node_text(abstract)
        if text:
            texts.append((text, "要約書"))
    return texts
