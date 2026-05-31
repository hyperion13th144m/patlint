from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text


class RuleInventionTitleTests(unittest.TestCase):
    def test_errors_when_dependent_claim_invention_name_differs_from_reference(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】特許請求の範囲",
                    "【請求項１】走行制御部を備えることを特徴とする自動車。",
                    "【請求項２】請求項１に記載の自動車。",
                    "【請求項３】請求項１に記載の自動運転方法。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertEqual(
            diagnostics[0].message,
            "請求項3の発明の名称 自動運転方法 は、参照元請求項の発明の名称と一致していません（参照元: 請求項1: 自動車）。",
        )
        self.assertEqual(diagnostics[0].location.claim_number, 3)

    def test_allows_dependent_claim_invention_name_matching_references(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】特許請求の範囲",
                    "【請求項１】走行制御部を備えることを特徴とする自動車。",
                    "【請求項２】請求項１に記載の自動車。",
                    "【請求項３】請求項１又は２に記載の自動車。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH"
                for diagnostic in result.diagnostics
            )
        )

    def test_reports_each_mismatched_reference_claim_invention_name(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】特許請求の範囲",
                    "【請求項１】ことを特徴とする自動車。",
                    "【請求項２】ことを特徴とする制御装置。",
                    "【請求項３】請求項１又は２に記載の自動運転方法。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(
            diagnostics[0].message,
            "請求項3の発明の名称 自動運転方法 は、参照元請求項の発明の名称と一致していません（参照元: 請求項1: 自動車, 請求項2: 制御装置）。",
        )

    def test_allows_matching_invention_title_and_independent_claim_terms(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の名称】自動車及び自動運転方法",
                    "【書類名】特許請求の範囲",
                    "【請求項１】走行制御部を備えることを特徴とする自動車。",
                    "【請求項２】請求項１に記載の自動車。",
                    "【請求項３】走行制御を行うことを特徴とする自動運転方法",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "INVENTION_TITLE_CLAIM_MISMATCH"
                for diagnostic in result.diagnostics
            )
        )

    def test_splits_invention_title_by_supported_delimiters(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の名称】自動車，制御装置ならびに自動運転方法",
                    "【書類名】特許請求の範囲",
                    "【請求項１】ことを特徴とする自動車。",
                    "【請求項２】ことを特徴とする制御装置。",
                    "【請求項３】ことを特徴とする自動運転方法。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "INVENTION_TITLE_CLAIM_MISMATCH"
                for diagnostic in result.diagnostics
            )
        )

    def test_errors_when_invention_title_and_independent_claim_terms_do_not_match(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の名称】自動車及び自動運転方法",
                    "【書類名】特許請求の範囲",
                    "【請求項１】走行制御部を備えることを特徴とする自動車。",
                    "【請求項２】請求項１に記載の自動車。",
                    "【請求項３】走行制御を行うことを特徴とする制御方法。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "INVENTION_TITLE_CLAIM_MISMATCH"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertEqual(
            diagnostics[0].message,
            "発明の名称と独立請求項の末尾語句が一致していません（発明の名称: 自動車, 自動運転方法 / 独立請求項: 自動車, 制御方法）。",
        )
        self.assertEqual(diagnostics[0].location.section_type, "invention_title")


if __name__ == "__main__":
    unittest.main()
