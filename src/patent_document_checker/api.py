from __future__ import annotations

import html
import json
from importlib import resources
from pathlib import Path
import sys
import uuid
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .data_paths import find_data_dirs
from .diagnostic_view import diagnostics_to_views
from .engine import check_ir
from .parser import PatentDocumentIR, parse_docx_bytes, parse_ooxml, parse_text
from .report.reference_signs import reference_sign_entries
from .terms import extract_document_terms_with_signs, extract_term_occurrences
from .units import extract_unit_checks

# In-memory document store: document_id -> PatentDocumentIR
_document_store: dict[str, PatentDocumentIR] = {}
# Overview results store: document_id -> OverviewResult（全体レビュー後に蓄積）
_overview_store: dict[str, Any] = {}


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

_addin_dir = _package_data_path("addin")
if _addin_dir is not None:
    app.mount(
        "/addin",
        StaticFiles(directory=str(_addin_dir)),
        name="word-addin",
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


# ---------------------------------------------------------------------------
# Document store endpoints
# ---------------------------------------------------------------------------

@app.post("/api/documents/upload-text")
def upload_text_document(request: TextCheckRequest) -> dict:
    document = parse_text(request.text, source=request.source)
    doc_id = str(uuid.uuid4())
    _document_store[doc_id] = document
    result = _document_response(document)
    result["document_id"] = doc_id
    return result


@app.post("/api/documents/upload-ooxml")
def upload_ooxml_document(request: OoxmlCheckRequest) -> dict:
    try:
        document = parse_ooxml(request.document_xml, source=request.source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc_id = str(uuid.uuid4())
    _document_store[doc_id] = document
    result = _document_response(document)
    result["document_id"] = doc_id
    return result


@app.post("/api/documents/upload-docx")
async def upload_docx_document(file: UploadFile = File(...)) -> dict:
    try:
        content = await file.read()
        document = parse_docx_bytes(content, source=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc_id = str(uuid.uuid4())
    _document_store[doc_id] = document
    result = _document_response(document)
    result["document_id"] = doc_id
    return result


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_document(document_id: str) -> PatentDocumentIR:
    doc = _document_store.get(document_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"ドキュメント {document_id} が見つかりません。先にアップロードしてください。",
        )
    return doc


# ---------------------------------------------------------------------------
# AI review request models
# ---------------------------------------------------------------------------

class AIReviewRequest(BaseModel):
    claim_numbers: list[int] | None = None
    provider: str = "anthropic"
    model: str | None = None
    anonymize: bool = True


class ParagraphReviewRequest(BaseModel):
    provider: str = "anthropic"
    model: str | None = None
    anonymize: bool = True


class OverviewReviewRequest(BaseModel):
    provider: str = "anthropic"
    model: str | None = None
    anonymize: bool = True


# ---------------------------------------------------------------------------
# AI review endpoints
# ---------------------------------------------------------------------------

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


@app.post("/api/documents/{document_id}/full-overview")
async def full_overview_endpoint(document_id: str, request: OverviewReviewRequest):
    """全体AIレビュー（SSE）。完了後に OverviewResult を保存し後続レビューに引き継ぐ。"""
    from .ai.client import get_ai_client
    from .ai.review import overview_review
    from .rules import run_document_rules

    document = _get_document(document_id)

    try:
        client = get_ai_client(provider=request.provider, model=request.model)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rule_diagnostics = run_document_rules(document)

    async def generate():
        yield _sse("start", {"review_type": "overview"})
        try:
            ai_diagnostics, overview, usage = await overview_review(
                document=document,
                client=client,
                rule_diagnostics=rule_diagnostics,
                do_anonymize=request.anonymize,
            )
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
            return

        _overview_store[document_id] = overview
        yield _sse("result", {
            "label": "全体",
            "overview": overview.to_dict(),
            "diagnostic_views": diagnostics_to_views(ai_diagnostics),
            "token_usage": {**usage, "total_tokens": usage["input_tokens"] + usage["output_tokens"]},
        })
        yield _sse("done", {
            "total_token_usage": {**usage, "total_tokens": usage["input_tokens"] + usage["output_tokens"]},
        })

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/api/documents/{document_id}/api-review")
async def api_review_endpoint(document_id: str, request: AIReviewRequest):
    """請求項別AIレビュー（SSE）。1請求項完了ごとにイベントを送信する。"""
    from .ai.client import get_ai_client
    from .ai.review import iter_claim_review
    from .rules import run_document_rules

    document = _get_document(document_id)
    claim_numbers = request.claim_numbers or [c.number for c in document.claims]
    overview = _overview_store.get(document_id)

    try:
        client = get_ai_client(provider=request.provider, model=request.model)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rule_diagnostics = run_document_rules(document)

    async def generate():
        total_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        yield _sse("start", {
            "review_type": "claim",
            "total": len(claim_numbers),
            "overview_used": overview is not None,
        })
        try:
            async for label, ai_diagnostics, usage in iter_claim_review(
                document=document,
                claim_numbers=claim_numbers,
                client=client,
                rule_diagnostics=rule_diagnostics,
                do_anonymize=request.anonymize,
                overview=overview,
            ):
                total_usage["input_tokens"] += usage["input_tokens"]
                total_usage["output_tokens"] += usage["output_tokens"]
                yield _sse("result", {
                    "label": label,
                    "diagnostic_views": diagnostics_to_views(ai_diagnostics),
                    "token_usage": {**usage, "total_tokens": usage["input_tokens"] + usage["output_tokens"]},
                })
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
            return

        total_usage["total_tokens"] = total_usage["input_tokens"] + total_usage["output_tokens"]
        yield _sse("done", {"total_token_usage": total_usage})

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


import re as _re
_PARA_HEADER_RE = _re.compile(r"^【\d{4}】")


def _description_block_indices(document: PatentDocumentIR) -> list[int]:
    """明細書セクションの【NNNN】段落のインデックスを返す。"""
    return [
        b.index
        for b in document.raw_blocks
        if b.section_type == "description" and _PARA_HEADER_RE.match(b.text)
    ]


@app.post("/api/documents/{document_id}/paragraph-review")
async def paragraph_review_endpoint(document_id: str, request: ParagraphReviewRequest):
    """段落別AIレビュー（SSE）。明細書の全【NNNN】段落を対象に1段落ずつ処理する。"""
    from .ai.client import get_ai_client
    from .ai.review import iter_paragraph_review
    from .rules import run_document_rules

    document = _get_document(document_id)
    block_indices = _description_block_indices(document)
    overview = _overview_store.get(document_id)

    try:
        client = get_ai_client(provider=request.provider, model=request.model)
    except (ImportError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rule_diagnostics = run_document_rules(document)

    async def generate():
        total_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        yield _sse("start", {
            "review_type": "paragraph",
            "total": len(block_indices),
            "overview_used": overview is not None,
        })
        try:
            async for label, ai_diagnostics, usage in iter_paragraph_review(
                document=document,
                block_indices=block_indices,
                client=client,
                rule_diagnostics=rule_diagnostics,
                do_anonymize=request.anonymize,
                overview=overview,
            ):
                total_usage["input_tokens"] += usage["input_tokens"]
                total_usage["output_tokens"] += usage["output_tokens"]
                yield _sse("result", {
                    "label": label,
                    "diagnostic_views": diagnostics_to_views(ai_diagnostics),
                    "token_usage": {**usage, "total_tokens": usage["input_tokens"] + usage["output_tokens"]},
                })
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
            return

        total_usage["total_tokens"] = total_usage["input_tokens"] + total_usage["output_tokens"]
        yield _sse("done", {"total_token_usage": total_usage})

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


def _merge_diagnostics(
    rule_diagnostics: list,
    ai_diagnostics: list,
) -> list:
    """ルールベース指摘 + AI指摘を統合。severityの高い順・location順に並べる。"""
    _severity_order = {"error": 0, "warning": 1, "info": 2}
    combined = list(rule_diagnostics) + list(ai_diagnostics)
    return sorted(
        combined,
        key=lambda d: (
            _severity_order.get(d.severity, 9),
            (d.location.claim_number or 9999) if d.location else 9999,
            d.rule_id,
        ),
    )


def _count_severities(diagnostics: list) -> dict:
    counts = {"error": 0, "warning": 0, "info": 0}
    for d in diagnostics:
        counts[d.severity] = counts.get(d.severity, 0) + 1
    return counts


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
            "blocks": [
                {"index": b.index, "text": b.text, "section_type": b.section_type}
                for b in document.raw_blocks
            ],
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
