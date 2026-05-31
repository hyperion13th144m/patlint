from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Protocol

CLAIM_TAG_RE = re.compile(r"【\s*請求項\s*([0-9０-９]+)\s*】")
SECTION_TAG_RE = re.compile(
    r"【\s*(発明の名称|技術分野|背景技術|発明の概要|図面の簡単な説明|発明を実施するための形態|符号の説明|書類名)\s*】"
)


class ClaimBlock(Protocol):
    index: int
    text: str


@dataclass(slots=True)
class Claim:
    number: int
    text: str
    block_index: int | None = None
    search_text: str | None = None
    referenced_claims: list[int] = field(default_factory=list)

    # multi-claim. この請求項が複数の請求項を参照している（直接的な multiple-dependence）
    is_multiple_dependent: bool = False

    # この請求項が multiple-dependence を参照している（直接的・間接的な multiple-dependence）
    references_multiple_dependent: bool = False

    # この請求項がマルチマルチクレームである。
    is_multi_multi: bool = False

    # この請求項がマルチマルチクレームを参照している（直接的・間接的なマルチマルチクレーム参照）
    references_multi_multi: bool = False


def normalize_digits(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def parse_claim_number(value: str) -> int:
    return int(normalize_digits(value))


def extract_claims(blocks: list[ClaimBlock]) -> list[Claim]:
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
        next_claim_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(joined)
        )
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
    compute_multi_multi_claim_states(claims)
    return claims


def compute_multi_multi_claim_states(claims: list[Claim]) -> None:
    by_number: dict[int, Claim] = {}

    for claim in claims:
        # Recompute derived official-checker states from a clean baseline.
        claim.references_multiple_dependent = False
        claim.is_multi_multi = False
        claim.references_multi_multi = False

        for referenced in claim.referenced_claims:
            referenced_claim = by_number.get(referenced)
            if referenced_claim is None:
                continue

            if (
                referenced_claim.is_multiple_dependent
                or referenced_claim.references_multiple_dependent
            ):
                claim.references_multiple_dependent = True

            if (
                referenced_claim.is_multi_multi
                or referenced_claim.references_multi_multi
            ):
                claim.references_multi_multi = True

        claim.is_multi_multi = (
            claim.is_multiple_dependent and claim.references_multiple_dependent
        )
        by_number[claim.number] = claim


def extract_claim_references(text: str) -> list[int]:
    normalized = normalize_digits(text)
    refs: list[int] = []
    for match in re.finditer(
        r"請求項\s*([0-9]+)(?P<trail>.*?)(?=請求項|[。\n]|$)", normalized
    ):
        first = int(match.group(1))
        trail = match.group("trail")
        refs.append(first)

        range_match = re.match(
            r"\s*(?:-|~|〜|乃至|ないし|から)\s*(?:請求項)?([0-9]+)", trail
        )
        if range_match:
            end = int(range_match.group(1))
            step = 1 if end >= first else -1
            refs.extend(range(first + step, end + step, step))
            continue

        for extra in re.finditer(
            r"(?:、|,|又は|または|若しくは|もしくは|及び|および|又ハ)\s*(?:請求項)?([0-9]+)(?:\s*(?:-|~|〜|乃至|ないし|から)\s*(?:請求項)?([0-9]+))?",
            trail,
        ):
            start = int(extra.group(1))
            refs.append(start)
            if extra.group(2):
                end = int(extra.group(2))
                step = 1 if end >= start else -1
                refs.extend(range(start + step, end + step, step))

    return _dedupe_preserving_order(refs)


def _block_index_for_offset(
    block_offsets: list[tuple[int, int]], target: int
) -> int | None:
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
