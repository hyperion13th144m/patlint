from __future__ import annotations

from collections import Counter

from patent_checker_common import Diagnostic, DiagnosticLocation

from .parser import Claim, PatentDocumentIR


def run_document_rules(document: PatentDocumentIR) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_claim_numbering(document.claims))
    diagnostics.extend(check_claim_dependency(document.claims))
    diagnostics.extend(check_multi_multi_claim(document.claims))
    return diagnostics


def check_claim_numbering(claims: list[Claim]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not claims:
        return [
            Diagnostic(
                rule_id="CLAIM_NUMBERING",
                severity="warning",
                message="請求項が見つかりません。",
                location=DiagnosticLocation(source_type="document", section_type="claims"),
                suggestion="【請求項1】の形式で請求項が記載されているか確認してください。",
            )
        ]

    counts = Counter(claim.number for claim in claims)
    by_number = {claim.number: claim for claim in claims}
    for number, count in sorted(counts.items()):
        if count > 1:
            claim = by_number[number]
            diagnostics.append(
                Diagnostic(
                    rule_id="CLAIM_NUMBERING",
                    severity="error",
                    message=f"請求項{number}が重複しています。",
                    location=_claim_location(claim),
                    suggestion="請求項番号を一意にしてください。",
                )
            )

    positive_numbers = [claim.number for claim in claims if claim.number > 0]
    if positive_numbers:
        for expected in range(1, max(positive_numbers) + 1):
            if expected not in counts:
                next_claim = next((claim for claim in claims if claim.number > expected), None)
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_NUMBERING",
                        severity="error",
                        message=f"請求項{expected}が欠落しています。",
                        location=_claim_location(next_claim) if next_claim else DiagnosticLocation(source_type="document", section_type="claims"),
                        suggestion="請求項番号が連続しているか確認してください。",
                    )
                )

    for claim in claims:
        if claim.number <= 0:
            diagnostics.append(
                Diagnostic(
                    rule_id="CLAIM_NUMBERING",
                    severity="error",
                    message=f"請求項番号{claim.number}は使用できません。",
                    location=_claim_location(claim),
                    suggestion="請求項番号は1以上の整数にしてください。",
                )
            )

    return diagnostics


def check_claim_dependency(claims: list[Claim]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    existing = {claim.number for claim in claims}

    for claim in claims:
        for referenced in claim.referenced_claims:
            if referenced not in existing:
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_DEPENDENCY",
                        severity="error",
                        message=f"請求項{claim.number}が存在しない請求項{referenced}を引用しています。",
                        location=_claim_location(claim),
                        suggestion="引用先の請求項番号を確認してください。",
                    )
                )
            elif referenced == claim.number:
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_DEPENDENCY",
                        severity="error",
                        message=f"請求項{claim.number}が自己引用しています。",
                        location=_claim_location(claim),
                        suggestion="自己引用にならないよう引用関係を修正してください。",
                    )
                )
            elif referenced > claim.number:
                diagnostics.append(
                    Diagnostic(
                        rule_id="CLAIM_DEPENDENCY",
                        severity="error",
                        message=f"請求項{claim.number}が後続の請求項{referenced}を引用しています。",
                        location=_claim_location(claim),
                        suggestion="先行する請求項のみを引用してください。",
                    )
                )

    return diagnostics


def check_multi_multi_claim(claims: list[Claim]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    by_number = {claim.number: claim for claim in claims}

    for claim in claims:
        if not claim.is_multiple_dependent:
            continue
        multi_refs = [
            referenced
            for referenced in claim.referenced_claims
            if by_number.get(referenced) and by_number[referenced].is_multiple_dependent
        ]
        if multi_refs:
            refs = "、".join(str(ref) for ref in multi_refs)
            diagnostics.append(
                Diagnostic(
                    rule_id="MULTI_MULTI_CLAIM",
                    severity="warning",
                    message=f"請求項{claim.number}が複数従属請求項{refs}を引用しています。",
                    location=_claim_location(claim),
                    suggestion="マルチマルチクレームに該当しないか確認してください。",
                )
            )

    return diagnostics


def _claim_location(claim: Claim | None) -> DiagnosticLocation:
    if claim is None:
        return DiagnosticLocation(source_type="document", section_type="claims")
    return DiagnosticLocation(
        source_type="document",
        section_type="claims",
        claim_number=claim.number,
        block_index=claim.block_index,
        search_text=claim.search_text,
    )
