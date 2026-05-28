from __future__ import annotations

import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from xml.etree import ElementTree


W_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CLAIM_TAG_RE = re.compile(r"【\s*請求項\s*([0-9０-９]+)\s*】")
SECTION_TAG_RE = re.compile(r"【\s*(発明の名称|技術分野|背景技術|発明の概要|図面の簡単な説明|発明を実施するための形態|符号の説明|要約書)\s*】")


@dataclass(slots=True)
class RawBlock:
    id: str
    index: int
    text: str
    section_type: str | None = None


@dataclass(slots=True)
class Claim:
    number: int
    text: str
    block_index: int | None = None
    search_text: str | None = None
    referenced_claims: list[int] = field(default_factory=list)
    is_multiple_dependent: bool = False


@dataclass(slots=True)
class PatentDocumentIR:
    source: str | None
    raw_blocks: list[RawBlock]
    claims: list[Claim]
    tree: object | None = None


def normalize_digits(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def parse_claim_number(value: str) -> int:
    return int(normalize_digits(value))


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


def extract_claims(blocks: list[RawBlock]) -> list[Claim]:
    parts: list[tuple[int, str, int | None, str]] = []
    joined = "\n".join(block.text for block in blocks)
    block_offsets: list[tuple[int, int]] = []
    offset = 0
    for block in blocks:
        block_offsets.append((offset, block.index))
        offset += len(block.text) + 1

    matches = list(CLAIM_TAG_RE.finditer(joined))
    for index, match in enumerate(matches):
        start = match.end()
        next_claim_start = matches[index + 1].start() if index + 1 < len(matches) else len(joined)
        section_match = SECTION_TAG_RE.search(joined, start, next_claim_start)
        end = section_match.start() if section_match else next_claim_start
        number = parse_claim_number(match.group(1))
        text = joined[start:end].strip()
        block_index = _block_index_for_offset(block_offsets, match.start())
        parts.append((number, text, block_index, match.group(0)))

    claims: list[Claim] = []
    for number, text, block_index, search_text in parts:
        refs = extract_claim_references(text)
        claims.append(
            Claim(
                number=number,
                text=text,
                block_index=block_index,
                search_text=search_text,
                referenced_claims=refs,
                is_multiple_dependent=len(set(refs)) > 1,
            )
        )
    return claims


def extract_claim_references(text: str) -> list[int]:
    normalized = normalize_digits(text)
    refs: list[int] = []
    for match in re.finditer(r"請求項\s*([0-9]+)(?P<trail>[^。\n]*)", normalized):
        first = int(match.group(1))
        trail = match.group("trail")
        refs.append(first)

        range_match = re.match(r"\s*(?:-|~|〜|乃至|ないし|から)\s*([0-9]+)", trail)
        if range_match:
            end = int(range_match.group(1))
            step = 1 if end >= first else -1
            refs.extend(range(first + step, end + step, step))
            continue

        for extra in re.finditer(r"(?:、|,|又は|または|若しくは|もしくは|及び|および|又ハ)\s*([0-9]+)", trail):
            refs.append(int(extra.group(1)))

    return _dedupe_preserving_order(refs)


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
        if CLAIM_TAG_RE.search(block.text):
            current = "claims"
        elif "【明細書】" in block.text:
            current = "description"
        elif "【要約書】" in block.text:
            current = "abstract"
        block.section_type = current


def _block_index_for_offset(block_offsets: list[tuple[int, int]], target: int) -> int | None:
    current: int | None = None
    for offset, block_index in block_offsets:
        if offset > target:
            break
        current = block_index
    return current


def _dedupe_preserving_order(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
