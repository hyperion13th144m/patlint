from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_checker_common import Diagnostic, DiagnosticLocation, DiagnosticsResult
from patent_document_checker.parser import Claim
from patent_document_checker.report import render_html_report
from patent_document_checker.terms import TermWithSign
from patent_document_checker.units import UnitCheckResult


class ReportTests(unittest.TestCase):
    def test_debug_terms_are_rendered_when_provided(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(
            result,
            term_occurrences={
                "CPUモジュール": ["請求項1"],
                "パルス印加部5": ["0001"],
            },
            debug_terms_by_claim={1: ["CPUモジュール", "制御装置"]},
            debug_terms_with_signs=[TermWithSign("パルス印加部5", "パルス印加部", "5", "0001")],
        )

        self.assertIn("語句出現表", html)
        self.assertIn("CPUモジュール", html)
        self.assertIn("請求項1", html)
        self.assertIn("パルス印加部5", html)
        self.assertLess(html.index("語句出現表"), html.index("Debug"))
        self.assertIn("抽出語句一覧", html)
        self.assertIn("請求項1", html)
        self.assertIn("CPUモジュール, 制御装置", html)
        self.assertIn("符号付語句一覧", html)
        self.assertIn("パルス印加部5", html)
        self.assertIn("0001", html)

    def test_claim_relationships_and_reference_signs_are_before_term_occurrences(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(
            result,
            claims=[Claim(number=1, text="装置。")],
            term_occurrences={"電極": ["0001"]},
            terms_with_signs=[TermWithSign("電極10", "電極", "10", "0001")],
        )

        claim_index = html.index("請求項の関係")
        reference_index = html.index("符号の説明用一覧")
        term_index = html.index("語句出現表")
        self.assertLess(claim_index, reference_index)
        self.assertLess(reference_index, term_index)

    def test_term_occurrences_are_sorted_by_term(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(
            result,
            term_occurrences={
                "流路部材30": ["要約書"],
                "CPUモジュール": ["請求項1"],
                "アルミ箔": ["0001"],
            },
        )

        self.assertLess(html.index("CPUモジュール"), html.index("アルミ箔"))
        self.assertLess(html.index("アルミ箔"), html.index("流路部材30"))

    def test_claim_relationships_are_rendered_for_html_report(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")
        claims = [
            Claim(number=1, text="装置。"),
            Claim(number=2, text="請求項1に記載の装置。", referenced_claims=[1]),
            Claim(
                number=3,
                text="請求項1又は2に記載の装置。",
                referenced_claims=[1, 2],
                is_multiple_dependent=True,
                references_multiple_dependent=True,
                is_multi_multi=True,
            ),
        ]

        html = render_html_report(result, claims=claims)

        self.assertIn("請求項の関係", html)
        self.assertIn("<th>従属先</th>", html)
        self.assertIn("<td>請求項1</td><td>－</td><td>請求項2、請求項3</td><td>独立項</td><td>－</td>", html)
        self.assertIn("<td>請求項2</td><td>請求項1</td><td>請求項3</td><td>従属項</td><td>－</td>", html)
        self.assertIn("<td>請求項3</td><td>請求項1、請求項2</td><td>－</td><td>複数従属項</td><td>マルチマルチ、複数従属項を引用</td>", html)

    def test_unit_checks_are_rendered_for_html_report(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(
            result,
            unit_checks=[
                UnitCheckResult(
                    line=3,
                    col=16,
                    matched="1.2atm",
                    number="1.2",
                    unit="atm",
                    level="WARNING",
                    message="非SI（気圧）：kPa または MPa を推奨",
                )
            ],
        )

        self.assertIn("単位チェック", html)
        self.assertIn("<td>1.2atm</td>", html)
        self.assertIn("<td>atm</td>", html)
        self.assertIn("非SI（気圧）：kPa または MPa を推奨", html)

    def test_reference_sign_list_is_rendered_for_html_report(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(
            result,
            terms_with_signs=[
                TermWithSign("冷却部20", "冷却部", "20", "0002"),
                TermWithSign("電極10", "電極", "10", "0001"),
                TermWithSign("補助部A-2", "補助部", "A-2", "要約書"),
                TermWithSign("電極10", "電極", "10", "0003"),
            ],
        )

        self.assertIn("符号の説明用一覧", html)
        self.assertIn("reference-output", html)
        self.assertIn("三点リーダ", html)
        self.assertIn("カンマ（，）", html)
        self.assertIn('value="__newline__"', html)
        self.assertNotIn('value="\\n"', html)
        self.assertIn('=== "__newline__" ? "\\n"', html)
        self.assertIn("昇順にソート", html)
        self.assertLess(html.index("<td>A-2</td>"), html.index("<td>10</td>"))
        self.assertLess(html.index("<td>10</td>"), html.index("<td>20</td>"))
        self.assertIn("0001、0003", html)


    def test_diagnostics_use_print_friendly_view(self) -> None:
        result = DiagnosticsResult(
            source="sample",
            product="document-checker",
            diagnostics=[
                Diagnostic(
                    rule_id="CLAIM_NUMBERING",
                    severity="error",
                    message="請求項2が欠落しています。",
                    location=DiagnosticLocation(source_type="document", section_type="claims"),
                    suggestion="請求項番号が連続しているか確認してください。",
                ),
                Diagnostic(
                    rule_id="PARAGRAPH_END_PUNCTUATION",
                    severity="warning",
                    message="段落の末尾が句点「。」で終わっていません。",
                    location=DiagnosticLocation(search_text="【0001】"),
                ),
            ],
        )

        html = render_html_report(result)

        self.assertIn("<tr><th>区分</th><th>ルール</th><th>内容</th></tr>", html)
        self.assertIn("severity-error", html)
        self.assertIn("severity-warning", html)
        self.assertIn("請求項番号", html)
        self.assertIn("段落末尾句点", html)
        self.assertIn("段落【0001】", html)
        self.assertNotIn("<th>Suggestion</th>", html)

    def test_debug_terms_are_omitted_by_default(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(result)

        self.assertNotIn("語句出現表", html)
        self.assertNotIn("抽出語句一覧", html)
        self.assertNotIn("符号付語句一覧", html)


if __name__ == "__main__":
    unittest.main()
