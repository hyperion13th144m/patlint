from __future__ import annotations

from patent_checker_common import Diagnostic, DiagnosticLocation

from .common import _node_text


def check_abstract_length(tree: object | None) -> list[Diagnostic]:
    if tree is None or not hasattr(tree, "find_all"):
        return []

    diagnostics: list[Diagnostic] = []
    for abstract in tree.find_all(kind="abstract_tag"):
        text = _node_text(abstract)
        length = len(text)
        if length <= 400:
            continue
        diagnostics.append(
            Diagnostic(
                rule_id="ABSTRACT_LENGTH",
                severity="error",
                message=f"要約書の文字数が400文字を超えています（{length}文字）。",
                location=DiagnosticLocation(
                    source_type="document",
                    section_type="abstract",
                    block_index=getattr(abstract, "block_index", None),
                    search_text="【要約】",
                ),
                suggestion="要約書を400文字以内にしてください。",
            )
        )

    return diagnostics
