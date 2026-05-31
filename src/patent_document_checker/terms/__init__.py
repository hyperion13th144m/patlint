from __future__ import annotations

from .claim_terms import (
    extract_claim_term_occurrences,
    extract_claim_terms,
    extract_claim_terms_by_number,
)
from .models import ClaimTermOccurrence, TermWithSign
from .normalization import normalize_term_text
from .occurrences import extract_term_occurrences
from .signed_terms import extract_document_terms_with_signs, extract_terms_with_signs

__all__ = [
    "ClaimTermOccurrence",
    "TermWithSign",
    "extract_claim_term_occurrences",
    "extract_claim_terms",
    "extract_claim_terms_by_number",
    "extract_document_terms_with_signs",
    "extract_term_occurrences",
    "extract_terms_with_signs",
    "normalize_term_text",
]
