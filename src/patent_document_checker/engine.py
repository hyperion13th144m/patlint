from __future__ import annotations

from patent_checker_common import DiagnosticsResult

from .parser import PatentDocumentIR, parse_docx_bytes, parse_ooxml, parse_text
from .rules import run_document_rules


PRODUCT = "document-checker"


def check_text(text: str, source: str | None = "text") -> DiagnosticsResult:
    return check_ir(parse_text(text, source=source))


def check_ooxml(document_xml: str, source: str | None = "document.xml") -> DiagnosticsResult:
    return check_ir(parse_ooxml(document_xml, source=source))


def check_docx_bytes(docx_bytes: bytes, source: str | None = None) -> DiagnosticsResult:
    return check_ir(parse_docx_bytes(docx_bytes, source=source))


def check_ir(document: PatentDocumentIR) -> DiagnosticsResult:
    return DiagnosticsResult(
        source=document.source,
        product=PRODUCT,
        diagnostics=run_document_rules(document),
    )
