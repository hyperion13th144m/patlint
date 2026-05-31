from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text


class RuleTermTests(unittest.TestCase):
    def test_warns_for_term_variations_with_same_suffix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】一端側１０と他端側２０を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】一端側と他端側を備える装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_VARIATION"
        ]
        self.assertIn(
            "語句 一端側 と 他端側 は、末尾「端側」が一致していますが先頭が異なります。",
            messages,
        )

    def test_warns_for_term_variations_with_same_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】アルミ箔１０とアルミ製２０を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】アルミ箔とアルミ製を備える装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_VARIATION"
        ]
        self.assertIn(
            "語句 アルミ箔 と アルミ製 は、先頭「アルミ」が一致していますが末尾が異なります。",
            messages,
        )

    def test_ignores_term_variations_with_long_unmatched_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス殺菌器処理槽１０と処理槽２０を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス殺菌器処理槽と処理槽を備える装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_VARIATION"
        ]
        self.assertNotIn(
            "語句 パルス殺菌器処理槽 と 処理槽 は、末尾「処理槽」が一致していますが先頭が異なります。",
            messages,
        )

    def test_warns_when_same_term_has_different_signs(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】パルス印加部６は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "TERM_SIGN_CONFLICT"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(
            diagnostics[0].message,
            "符号付語句 パルス印加部 は、複数の符号で記載されています（5: 0001, 要約書、6: 0002）。",
        )

    def test_allows_same_term_with_same_sign_in_multiple_locations(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】パルス印加部５は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "TERM_SIGN_CONFLICT"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_same_sign_has_different_terms(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】制御部５は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "SIGN_TERM_CONFLICT"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(
            diagnostics[0].message,
            "符号 5 は、複数の語句で記載されています（パルス印加部: 0001, 要約書、制御部: 0002）。",
        )

    def test_allows_same_sign_with_same_term_in_multiple_locations(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理を実行する。",
                    "【０００２】パルス印加部５は別の処理を実行する。",
                    "【書類名】要約書",
                    "【要約】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "SIGN_TERM_CONFLICT"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_claim_term_is_missing_from_embodiments(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_IN_EMBODIMENTS"
        ]
        self.assertIn("請求項の語句 CPUモジュールは、実施形態に記載されていません", messages)
        self.assertNotIn("請求項の語句 制御部は、実施形態に記載されていません", messages)

    def test_allows_claim_terms_found_in_embodiments(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】CPUモジュールと制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_IN_EMBODIMENTS"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_claim_term_is_missing_from_tech_solution(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の概要】",
                    "【課題を解決するための手段】",
                    "【０００１】制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_IN_TECH_SOLUTION"
        ]
        self.assertIn("請求項の語句 CPUモジュールは、解決手段に記載されていません", messages)
        self.assertNotIn("請求項の語句 制御部は、解決手段に記載されていません", messages)

    def test_allows_claim_terms_found_in_tech_solution(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の概要】",
                    "【課題を解決するための手段】",
                    "【０００１】CPUモジュールと制御部は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールと制御部を備えるシステム。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_IN_TECH_SOLUTION"
                for diagnostic in result.diagnostics
            )
        )


if __name__ == "__main__":
    unittest.main()
