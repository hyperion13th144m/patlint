from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .engine import check_docx_bytes, check_ooxml, check_text


app = FastAPI(title="Patent Document Checker", version="0.1.0")


class TextCheckRequest(BaseModel):
    text: str
    source: str | None = "text"


class OoxmlCheckRequest(BaseModel):
    document_xml: str
    source: str | None = "document.xml"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "document-checker"}


@app.post("/api/check-text")
def check_text_endpoint(request: TextCheckRequest) -> dict:
    return check_text(request.text, source=request.source).to_dict()


@app.post("/api/check-ooxml")
def check_ooxml_endpoint(request: OoxmlCheckRequest) -> dict:
    try:
        return check_ooxml(request.document_xml, source=request.source).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/check-docx")
async def check_docx_endpoint(file: UploadFile = File(...)) -> dict:
    try:
        content = await file.read()
        return check_docx_bytes(content, source=file.filename).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
