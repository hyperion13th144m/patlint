from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text


class RuleFigureTests(unittest.TestCase):
    def test_warns_for_listed_figure_not_mentioned_in_spec(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【図面の簡単な説明】",
                    "【０００１】【図１】装置の正面図である。【図２】装置の側面図である。",
                    "【発明を実施するための形態】",
                    "【０００２】図１に示すように、装置は制御部を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "FIGURE_REFERENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(diagnostics[0].message, "図2は明細書で言及されていません。")
        self.assertEqual(diagnostics[0].location.section_type, "description_of_drawings")
        self.assertEqual(diagnostics[0].location.search_text, "【図2】")

    def test_warns_for_mentioned_figure_missing_from_drawings_description(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【図面の簡単な説明】",
                    "【０００１】【図１】装置の正面図である。",
                    "【発明を実施するための形態】",
                    "【０００２】図１及び図３に示すように、装置は制御部を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "FIGURE_REFERENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(
            diagnostics[0].message,
            "図3は明細書で言及されていますが、図面の簡単な説明に記載されていません。",
        )
        self.assertEqual(diagnostics[0].location.search_text, "【0002】")

    def test_expands_figure_reference_ranges(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【図面の簡単な説明】",
                    "【０００１】【図１】正面図である。【図２】側面図である。【図３】断面図である。【図４】説明図である。【図５】変形例である。",
                    "【発明を実施するための形態】",
                    "【０００２】図１から図４に示す構成と、図１～５に示す変形例と、図１～図５に示す範囲を説明する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "FIGURE_REFERENCE"
                for diagnostic in result.diagnostics
            )
        )


if __name__ == "__main__":
    unittest.main()
