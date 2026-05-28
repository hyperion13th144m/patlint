from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Severity = Literal["error", "warning", "info"]
SourceType = Literal["document", "drawing", "common"]


@dataclass(slots=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DiagnosticLocation:
    source_type: SourceType | None = None
    section_type: str | None = None
    claim_number: int | None = None
    block_id: str | None = None
    block_index: int | None = None
    search_text: str | None = None
    figure_id: str | None = None
    image_file: str | None = None
    bbox: BoundingBox | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class Diagnostic:
    rule_id: str
    severity: Severity
    message: str
    location: DiagnosticLocation | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class ReferenceSignLocation:
    section_type: str | None = None
    paragraph_index: int | None = None
    claim_number: int | None = None
    text_snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class ReferenceSign:
    sign: str
    label: str | None = None
    source: Literal["description", "claims", "abstract", "unknown"] = "unknown"
    locations: list[ReferenceSignLocation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DrawingSign:
    sign: str
    raw_text: str
    normalized_sign: str
    confidence: float | None = None
    figure_id: str | None = None
    image_file: str | None = None
    bbox: BoundingBox | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class DiagnosticsResult:
    source: str | None
    product: str
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts = {"error": 0, "warning": 0, "info": 0}
        for diagnostic in self.diagnostics:
            counts[diagnostic.severity] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "product": self.product,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "summary": self.summary,
        }
        if self.source is not None:
            data["source"] = self.source
        return data


@dataclass(slots=True)
class SignCompareResult:
    spec_signs: list[ReferenceSign] = field(default_factory=list)
    drawing_signs: list[DrawingSign] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
