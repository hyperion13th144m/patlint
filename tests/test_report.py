from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_checker_common import DiagnosticsResult
from patent_document_checker.report import render_html_report
from patent_document_checker.terms import TermWithSign


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

    def test_debug_terms_are_omitted_by_default(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(result)

        self.assertNotIn("語句出現表", html)
        self.assertNotIn("抽出語句一覧", html)
        self.assertNotIn("符号付語句一覧", html)


if __name__ == "__main__":
    unittest.main()
