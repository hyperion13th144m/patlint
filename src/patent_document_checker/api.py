from __future__ import annotations

import html
from importlib import resources
from pathlib import Path
import sys

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .data_paths import find_data_dirs
from .diagnostic_view import diagnostics_to_views
from .engine import check_ir
from .parser import PatentDocumentIR, parse_docx_bytes, parse_ooxml, parse_text
from .report.reference_signs import reference_sign_entries
from .terms import extract_document_terms_with_signs, extract_term_occurrences
from .units import extract_unit_checks


def _package_data_path(*parts: str) -> Path | None:
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root, "patent_document_checker", *parts))
    candidates.append(Path(__file__).resolve().parent.joinpath(*parts))

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


app = FastAPI(title="PatLint", version="0.1.0")
_ui_assets_dir = _package_data_path("ui", "assets")
if _ui_assets_dir is not None:
    app.mount(
        "/ui/assets",
        StaticFiles(directory=str(_ui_assets_dir)),
        name="ui-assets",
    )


class TextCheckRequest(BaseModel):
    text: str
    source: str | None = "text"


class OoxmlCheckRequest(BaseModel):
    document_xml: str
    source: str | None = "document.xml"


@app.get("/ui", response_class=HTMLResponse)
def ui() -> HTMLResponse:
    index_path = _package_data_path("ui", "index.html")
    if index_path is not None:
        html = index_path.read_text(encoding="utf-8")
    else:
        html = (
            resources.files("patent_document_checker.ui")
            .joinpath("index.html")
            .read_text(encoding="utf-8")
        )
    return HTMLResponse(html)


@app.get("/help", response_class=HTMLResponse)
def help_page() -> HTMLResponse:
    return HTMLResponse(_default_words_help_html())


def _default_words_help_html() -> str:
    template_path = _package_data_path("ui", "help.html")
    if template_path is not None:
        template = template_path.read_text(encoding="utf-8")
    else:
        template = (
            resources.files("patent_document_checker.ui")
            .joinpath("help.html")
            .read_text(encoding="utf-8")
        )
    return template.replace("{{WORD_FILE_SECTIONS}}", _word_file_sections_html())


def _word_file_sections_html() -> str:
    files = ("default.json", "default-terms.txt", "extra.txt")
    sections = []
    for filename in files:
        content = _read_first_words_file(filename)
        body = html.escape(content if content is not None else "ファイルが見つかりません。")
        sections.append(
            f"""
      <section class="file-section">
        <h3>{html.escape(filename)}</h3>
        <pre>{body}</pre>
      </section>"""
        )
    return "".join(sections)


def _read_first_words_file(filename: str) -> str | None:
    for words_dir in find_data_dirs("words", anchor=Path(__file__)):
        path = words_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


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
    check_result = check_ir(document)
    result = check_result.to_dict()
    terms_with_signs = extract_document_terms_with_signs(document.tree)
    result.update(
        {
            "diagnostic_views": diagnostics_to_views(check_result.diagnostics),
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
