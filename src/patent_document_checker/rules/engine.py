from __future__ import annotations

from patent_checker_common import Diagnostic

from ..parser import PatentDocumentIR
from .abstract import check_abstract_length
from .claim_dependencies import check_claim_dependency, check_multi_multi_claim
from .claim_numbering import check_claim_numbering
from .claim_term_reference import check_missing_claim_term_reference_prefix
from .claim_terms_in_sections import (
    check_claim_terms_in_embodiments,
    check_claim_terms_in_tech_solution,
)
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


def run_document_rules(document: PatentDocumentIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_forbidden_characters(document.raw_blocks))
    diagnostics.extend(check_recommended_wording(document))
    diagnostics.extend(check_paragraph_numbering(document.tree))
    diagnostics.extend(check_paragraph_end_punctuation(document.tree))
    diagnostics.extend(check_claim_numbering(document.claims))
    diagnostics.extend(check_claim_dependency(document.claims))
    diagnostics.extend(check_multi_multi_claim(document.claims))
    diagnostics.extend(check_missing_claim_term_reference_prefix(document.claims))
    diagnostics.extend(check_term_variations(document.claims, document.tree))
    diagnostics.extend(check_term_sign_conflicts(document.tree))
    diagnostics.extend(check_claim_terms_in_embodiments(document.claims, document.tree))
    diagnostics.extend(check_claim_terms_in_tech_solution(document.claims, document.tree))
    diagnostics.extend(check_long_embodiment_sentences(document.tree))
    diagnostics.extend(check_missing_subject_in_embodiment_sentences(document.tree))
    diagnostics.extend(check_abstract_length(document.tree))
    diagnostics.extend(check_invention_title_matches_independent_claims(document.claims, document.tree))
    diagnostics.extend(check_dependent_claim_invention_name_matches_references(document.claims))
    diagnostics.extend(check_figure_references(document.tree))
    return diagnostics
