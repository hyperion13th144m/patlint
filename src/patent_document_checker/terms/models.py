from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TermWithSign:
    whole_string: str
    term: str
    sign: str
    source: str | None = None


@dataclass(frozen=True, slots=True)
class ClaimTermOccurrence:
    term: str
    has_reference_prefix: bool
    start: int
    end: int
