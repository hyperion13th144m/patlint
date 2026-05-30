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
            debug_terms_by_claim={1: ["CPUモジュール", "制御装置"]},
            debug_terms_with_signs=[TermWithSign("パルス印加部5", "パルス印加部", "5", "0001")],
        )

        self.assertIn("抽出語句一覧", html)
        self.assertIn("請求項1", html)
        self.assertIn("CPUモジュール, 制御装置", html)
        self.assertIn("符号付語句一覧", html)
        self.assertIn("パルス印加部5", html)
        self.assertIn("0001", html)

    def test_debug_terms_are_omitted_by_default(self) -> None:
        result = DiagnosticsResult(source="sample", product="document-checker")

        html = render_html_report(result)

        self.assertNotIn("抽出語句一覧", html)
        self.assertNotIn("符号付語句一覧", html)


if __name__ == "__main__":
    unittest.main()
