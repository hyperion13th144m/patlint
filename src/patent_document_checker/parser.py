from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree

from .claim_parser import Claim, extract_claims

W_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
APPLICATION_FORM_TAG_RE = re.compile(r"【書類名】\s*特許願")
CLAIMS_TAG_RE = re.compile(r"【書類名】\s*特許請求の範囲")
DESCRIPTION_TAG_RE = re.compile(r"【書類名】\s*明細書")
ABSTRACT_TAG_RE = re.compile(r"【書類名】\s*要約書")


@dataclass(slots=True)
class RawBlock:
    id: str
    index: int
    text: str
    section_type: str | None = None


@dataclass(slots=True)
class PatentDocumentIR:
    source: str | None
    raw_blocks: list[RawBlock]
    claims: list[Claim]
    tree: object | None = None


def parse_docx_bytes(docx_bytes: bytes, source: str | None = None) -> PatentDocumentIR:
    try:
        with zipfile.ZipFile(BytesIO(docx_bytes)) as archive:
            document_xml = archive.read("word/document.xml")
    except KeyError as exc:
        raise ValueError("word/document.xml が見つかりません。") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError("有効な .docx ファイルではありません。") from exc

    return parse_ooxml(document_xml.decode("utf-8"), source=source)


def parse_ooxml(document_xml: str, source: str | None = None) -> PatentDocumentIR:
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise ValueError("OOXML document.xml を解析できません。") from exc

    blocks: list[RawBlock] = []
    for paragraph in root.iter(f"{W_NAMESPACE}p"):
        text = _paragraph_text(paragraph).strip()
        if text:
            blocks.append(RawBlock(id=f"b{len(blocks)}", index=len(blocks), text=text))

    return build_ir(blocks, source=source)


def parse_text(text: str, source: str | None = None) -> PatentDocumentIR:
    blocks = [
        RawBlock(id=f"b{index}", index=index, text=line.strip())
        for index, line in enumerate(text.splitlines())
        if line.strip()
    ]
    if not blocks and text.strip():
        blocks = [RawBlock(id="b0", index=0, text=text.strip())]
    return build_ir(blocks, source=source)


def build_ir(blocks: list[RawBlock], source: str | None = None) -> PatentDocumentIR:
    from .structured_parser import parse_blocks_to_tree

    _annotate_sections(blocks)
    tree = parse_blocks_to_tree(blocks)
    claims = extract_claims(blocks)
    return PatentDocumentIR(source=source, raw_blocks=blocks, claims=claims, tree=tree)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    chunks: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{W_NAMESPACE}t" and node.text:
            chunks.append(node.text)
        elif node.tag == f"{W_NAMESPACE}tab":
            chunks.append("\t")
        elif node.tag == f"{W_NAMESPACE}br":
            chunks.append("\n")
    return "".join(chunks)


def _annotate_sections(blocks: list[RawBlock]) -> None:
    current: str | None = None
    for block in blocks:
        if APPLICATION_FORM_TAG_RE.search(block.text):
            current = "application_form"
        elif CLAIMS_TAG_RE.search(block.text):
            current = "claims"
        elif DESCRIPTION_TAG_RE.search(block.text):
            current = "description"
        elif ABSTRACT_TAG_RE.search(block.text):
            current = "abstract"
        block.section_type = current
