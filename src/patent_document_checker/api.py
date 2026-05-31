from __future__ import annotations

from importlib import resources

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .engine import check_ir
from .parser import PatentDocumentIR, parse_docx_bytes, parse_ooxml, parse_text
from .report.reference_signs import reference_sign_entries
from .terms import extract_document_terms_with_signs, extract_term_occurrences
from .units import extract_unit_checks


app = FastAPI(title="Patent Document Checker", version="0.1.0")


class TextCheckRequest(BaseModel):
    text: str
    source: str | None = "text"


class OoxmlCheckRequest(BaseModel):
    document_xml: str
    source: str | None = "document.xml"


@app.get("/ui", response_class=HTMLResponse)
def ui() -> HTMLResponse:
    html = (
        resources.files("patent_document_checker.ui")
        .joinpath("index.html")
        .read_text(encoding="utf-8")
    )
    return HTMLResponse(html)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "document-checker"}


@app.post("/api/check-text")
def check_text_endpoint(request: TextCheckRequest) -> dict:
    document = parse_text(request.text, source=request.source)
    return _document_response(document)


@app.post("/api/check-ooxml")
def check_ooxml_endpoint(request: OoxmlCheckRequest) -> dict:
    try:
        document = parse_ooxml(request.document_xml, source=request.source)
        return _document_response(document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/check-docx")
async def check_docx_endpoint(file: UploadFile = File(...)) -> dict:
    try:
        content = await file.read()
        document = parse_docx_bytes(content, source=file.filename)
        return _document_response(document)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _document_response(document: PatentDocumentIR) -> dict:
    result = check_ir(document).to_dict()
    terms_with_signs = extract_document_terms_with_signs(document.tree)
    result.update(
        {
            "term_occurrences": extract_term_occurrences(document.claims, document.tree),
            "claims": [_claim_to_dict(claim) for claim in document.claims],
            "unit_checks": [item.to_dict() for item in extract_unit_checks(document)],
            "terms_with_signs": [_term_with_sign_to_dict(item) for item in terms_with_signs],
            "reference_sign_entries": reference_sign_entries(terms_with_signs),
        }
    )
    return result


def _claim_to_dict(claim: object) -> dict:
    return {
        "number": getattr(claim, "number"),
        "text": getattr(claim, "text"),
        "referenced_claims": list(getattr(claim, "referenced_claims", [])),
        "is_multiple_dependent": getattr(claim, "is_multiple_dependent", False),
        "references_multiple_dependent": getattr(
            claim, "references_multiple_dependent", False
        ),
        "is_multi_multi": getattr(claim, "is_multi_multi", False),
        "references_multi_multi": getattr(claim, "references_multi_multi", False),
    }


def _term_with_sign_to_dict(item: object) -> dict:
    return {
        "source": getattr(item, "source", None),
        "whole_string": getattr(item, "whole_string", ""),
        "term": getattr(item, "term", ""),
        "sign": getattr(item, "sign", ""),
    }
