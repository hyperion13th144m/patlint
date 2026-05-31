from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text


class RuleWordingTests(unittest.TestCase):
    def test_warns_for_recommended_wording_in_claims_and_spec(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】Googleを用い、安全に処理する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】実質的に適切な制御部を備える装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id.startswith("RECOMMENDED_WORDING_")
        ]

        messages = [diagnostic.message for diagnostic in diagnostics]
        self.assertIn(
            "推奨されない語句・表現 適切 が含まれています（カテゴリ: claims_ng、適切）。",
            messages,
        )
        self.assertIn(
            "推奨されない語句・表現 実質的に が含まれています（カテゴリ: claims_ng、曖昧表現：実質的に）。",
            messages,
        )
        self.assertIn(
            "推奨されない語句・表現 Google が含まれています（カテゴリ: spec_trademark、Google）。",
            messages,
        )
        self.assertIn(
            "推奨されない語句・表現 安全 が含まれています（カテゴリ: spec_pl、安全）。",
            messages,
        )
        self.assertTrue(
            any(
                diagnostic.location.claim_number == 1
                and diagnostic.rule_id == "RECOMMENDED_WORDING_CLAIMS_NG"
                for diagnostic in diagnostics
            )
        )
        self.assertTrue(
            any(
                diagnostic.location.search_text == "【0001】"
                and diagnostic.rule_id == "RECOMMENDED_WORDING_SPEC_TRADEMARK"
                for diagnostic in diagnostics
            )
        )

    def test_warns_for_extra_words_and_typo_regex_patterns(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】Xerox装置はシュミレーションを行う。。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】適宜制御する装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id.startswith("RECOMMENDED_WORDING_")
        ]
        messages = [diagnostic.message for diagnostic in diagnostics]

        self.assertIn(
            "推奨されない語句・表現 適宜 が含まれています（カテゴリ: claims_ng、適宜）。",
            messages,
        )
        self.assertIn(
            "推奨されない語句・表現 Xerox が含まれています（カテゴリ: spec_trademark、Xerox）。",
            messages,
        )
        self.assertIn(
            "推奨されない語句・表現 シュミレーション が含まれています（カテゴリ: typo_regex、誤記：シミュレーション）。",
            messages,
        )
        self.assertIn(
            "推奨されない語句・表現 。。 が含まれています（カテゴリ: typo_regex、句点の重複）。",
            messages,
        )

    def test_does_not_apply_spec_only_wording_rules_to_claims(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】特許請求の範囲",
                    "【請求項１】Googleと安全な装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id in {
                    "RECOMMENDED_WORDING_SPEC_TRADEMARK",
                    "RECOMMENDED_WORDING_SPEC_PL",
                }
                for diagnostic in result.diagnostics
            )
        )

    def test_reports_forbidden_characters_as_errors(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【０００１】第①部材は半角ｶﾅと合成用丸⃝と髙さを含む。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "FORBIDDEN_CHARACTER"
        ]

        self.assertEqual([diagnostic.severity for diagnostic in diagnostics], ["error"] * 5)
        self.assertEqual(
            [diagnostic.location.search_text for diagnostic in diagnostics],
            ["①", "ｶ", "ﾅ", "⃝", "髙"],
        )
        self.assertEqual(
            [diagnostic.message for diagnostic in diagnostics],
            [
                "使用できない文字 ① が含まれています（丸付数字、位置: 8文字目）。",
                "使用できない文字 ｶ が含まれています（半角カナ、位置: 14文字目）。",
                "使用できない文字 ﾅ が含まれています（半角カナ、位置: 15文字目）。",
                "使用できない文字 ⃝ が含まれています（合成用丸、位置: 21文字目）。",
                "使用できない文字 髙 が含まれています（Shift_JISに変換できない文字、位置: 23文字目）。",
            ],
        )

    def test_allows_jis_x0208_shift_jis_characters_and_ascii_space(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【０００１】ASCII text と漢字、ひらがな、カタカナ、記号○～－∥￢を含む。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "FORBIDDEN_CHARACTER"
                for diagnostic in result.diagnostics
            )
        )


if __name__ == "__main__":
    unittest.main()
