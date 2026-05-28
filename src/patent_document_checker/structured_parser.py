from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from .parser import RawBlock


TAG_RE = re.compile(r"【[^】]+】")
NUMBER_RE = re.compile(r"^[0-9０-９]+$")
CLAIM_RE = re.compile(r"^請求項\s*([0-9０-９]+)$")
FIGURE_RE = re.compile(r"^図\s*([0-9０-９]+)$")
PATENT_LITERATURE_RE = re.compile(r"^(特許文献|非特許文献)\s*([0-9０-９]+)$")
FORMULA_RE = re.compile(r"^(数|表|化)\s*([0-9０-９]+)$")

MAJOR_TAGS = {
    "発明の名称",
    "技術分野",
    "背景技術",
    "先行技術文献",
    "発明の概要",
    "図面の簡単な説明",
    "発明を実施するための形態",
    "産業上の利用可能性",
    "符号の説明",
    "配列表フリーテキスト",
    "配列表",
}

SUBSECTION_TAGS = {
    "特許文献",
    "非特許文献",
    "発明が解決しようとする課題",
    "課題を解決するための手段",
    "発明の効果",
    "課題",
    "解決手段",
    "選択図",
}

APPLICATION_CONTAINER_TAGS = {
    "発明者",
    "出願人",
    "代理人",
}

APPLICATION_FIELD_TAGS = {
    "住所又は居所",
    "氏名",
    "識別番号",
    "名称",
    "電話番号",
    "整理番号",
    "あて先",
    "国際特許分類",
}


@dataclass(slots=True)
class PatentNode:
    tag: str | None = None
    tag_name: str | None = None
    text: str = ""
    kind: str = "text"
    level: int = 0
    number: int | None = None
    block_index: int | None = None
    children: list["PatentNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"kind": self.kind, "level": self.level}
        if self.tag is not None:
            data["jpTag"] = self.tag
        if self.tag_name is not None:
            data["tagName"] = self.tag_name
        if self.number is not None:
            data["number"] = self.number
        if self.text:
            data["text"] = self.text
        if self.block_index is not None:
            data["blockIndex"] = self.block_index
        if self.children:
            data["children"] = [child.to_dict() for child in self.children]
        return data

    def find_all(self, kind: str | None = None, tag_name: str | None = None) -> list["PatentNode"]:
        matches: list[PatentNode] = []
        if (kind is None or self.kind == kind) and (tag_name is None or self.tag_name == tag_name):
            matches.append(self)
        for child in self.children:
            matches.extend(child.find_all(kind=kind, tag_name=tag_name))
        return matches


def parse_blocks_to_tree(blocks: list[RawBlock]) -> PatentNode:
    root = PatentNode(kind="root", level=0)
    stack: list[PatentNode] = [root]

    for block in blocks:
        for tag, text in _split_tagged_text(block.text):
            if tag is None:
                _append_text(stack[-1], text, block.index)
                continue

            tag_name = _normalize_tag_name(tag)
            kind = classify_tag(tag_name)
            level = tag_level(kind, stack)
            node = PatentNode(
                tag=tag,
                tag_name=tag_name,
                text=text.strip(),
                kind=kind,
                level=level,
                number=extract_tag_number(kind, tag_name),
                block_index=block.index,
            )
            _push_node(stack, node)

    return root


def classify_tag(tag_name: str) -> str:
    if tag_name == "書類名":
        return "document"
    if CLAIM_RE.match(tag_name):
        return "claim"
    if NUMBER_RE.match(tag_name):
        return "paragraph"
    if FIGURE_RE.match(tag_name):
        return "figure"
    if PATENT_LITERATURE_RE.match(tag_name):
        return "literature_item"
    if FORMULA_RE.match(tag_name):
        return "embedded_object"
    if tag_name in MAJOR_TAGS:
        return "section"
    if tag_name in SUBSECTION_TAGS or tag_name.startswith("実施例"):
        return "subsection"
    if tag_name in APPLICATION_CONTAINER_TAGS:
        return "application_container"
    if tag_name in APPLICATION_FIELD_TAGS:
        return "application_field"
    return "tag"


def tag_level(kind: str, stack: list[PatentNode]) -> int:
    if kind == "document":
        return 1
    if kind == "claim":
        return 2 if _current_document_text(stack) == "特許請求の範囲" else 4
    if kind == "paragraph":
        return 4
    if kind in {"figure", "literature_item", "embedded_object"}:
        return 5
    if kind == "section":
        return 2
    if kind in {"subsection", "application_field"}:
        return 3
    if kind == "application_container":
        return 2
    if _current_document_text(stack) == "要約書":
        return 2
    return 3


def extract_tag_number(kind: str, tag_name: str) -> int | None:
    if kind == "paragraph" and NUMBER_RE.match(tag_name):
        return int(unicodedata.normalize("NFKC", tag_name))
    for pattern in (CLAIM_RE, FIGURE_RE, PATENT_LITERATURE_RE, FORMULA_RE):
        match = pattern.match(tag_name)
        if match:
            return int(unicodedata.normalize("NFKC", match.group(match.lastindex or 1)))
    return None


def _split_tagged_text(text: str) -> list[tuple[str | None, str]]:
    result: list[tuple[str | None, str]] = []
    matches = list(TAG_RE.finditer(text))
    if not matches:
        stripped = text.strip()
        return [(None, stripped)] if stripped else []

    if matches[0].start() > 0:
        prefix = text[: matches[0].start()].strip()
        if prefix:
            result.append((None, prefix))

    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        suffix = text[match.end() : next_start].strip()
        result.append((match.group(0), suffix))
    return result


def _push_node(stack: list[PatentNode], node: PatentNode) -> None:
    while stack and stack[-1].level >= node.level:
        stack.pop()
    stack[-1].children.append(node)
    stack.append(node)


def _append_text(parent: PatentNode, text: str, block_index: int) -> None:
    stripped = text.strip()
    if not stripped:
        return
    if parent.tag is not None and not parent.children:
        parent.text = f"{parent.text}\n{stripped}".strip() if parent.text else stripped
        return
    parent.children.append(PatentNode(text=stripped, kind="text", level=parent.level + 1, block_index=block_index))


def _normalize_tag_name(tag: str) -> str:
    name = tag.strip()[1:-1].strip()
    return unicodedata.normalize("NFKC", re.sub(r"\s+", "", name))


def _current_document_text(stack: list[PatentNode]) -> str | None:
    for node in reversed(stack):
        if node.kind == "document":
            return node.text
    return None
