from __future__ import annotations

from .abstract import check_abstract_length
from .claim_dependencies import check_claim_dependency, check_multi_multi_claim
from .claim_numbering import check_claim_numbering
from .claim_term_reference import check_missing_claim_term_reference_prefix
from .claim_terms_in_sections import (
    check_claim_terms_in_embodiments,
    check_claim_terms_in_tech_solution,
)
from .engine import run_document_rules
from .figures import check_figure_references
from .forbidden_characters import check_forbidden_characters
from .invention_title import (
    check_dependent_claim_invention_name_matches_references,
    check_invention_title_matches_independent_claims,
)
from .paragraphs import (
    check_long_embodiment_sentences,
    check_missing_subject_in_embodiment_sentences,
    check_paragraph_end_punctuation,
    check_paragraph_numbering,
)
from .recommended_wording import check_recommended_wording
from .term_sign_conflicts import check_term_sign_conflicts
from .term_variations import check_term_variations

__all__ = [
    "check_abstract_length",
    "check_claim_dependency",
    "check_claim_numbering",
    "check_claim_terms_in_embodiments",
    "check_claim_terms_in_tech_solution",
    "check_dependent_claim_invention_name_matches_references",
    "check_figure_references",
    "check_forbidden_characters",
    "check_invention_title_matches_independent_claims",
    "check_long_embodiment_sentences",
    "check_missing_claim_term_reference_prefix",
    "check_missing_subject_in_embodiment_sentences",
    "check_multi_multi_claim",
    "check_paragraph_end_punctuation",
    "check_paragraph_numbering",
    "check_recommended_wording",
    "check_term_sign_conflicts",
    "check_term_variations",
    "run_document_rules",
]
