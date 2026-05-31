from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text


class RuleClaimTests(unittest.TestCase):
    def test_reports_missing_duplicate_self_and_future_references(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項3】請求項3に記載の装置。",
                    "【請求項3】請求項4に記載の装置。",
                ]
            )
        )

        messages = [diagnostic.message for diagnostic in result.diagnostics]
        self.assertIn("請求項2が欠落しています。", messages)
        self.assertIn("請求項3が重複しています。", messages)
        self.assertIn("請求項3が自己引用しています。", messages)
        self.assertIn("請求項3が存在しない請求項4を引用しています。", messages)

    def test_reports_multi_multi_claim(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項2】装置。",
                    "【請求項3】請求項1又は2に記載の装置。",
                    "【請求項4】請求項2又は3に記載の装置。",
                ]
            )
        )

        self.assertTrue(any(diagnostic.rule_id == "MULTI_MULTI_CLAIM" for diagnostic in result.diagnostics))

    def test_reports_indirect_official_multi_multi_claim(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項2】請求項1に記載の装置。",
                    "【請求項3】請求項1又は2に記載の装置。",
                    "【請求項4】請求項3に記載の装置。",
                    "【請求項5】請求項2又は4に記載の装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "MULTI_MULTI_CLAIM"
        ]
        self.assertEqual(messages, ["請求項5がマルチマルチクレームとして検出されました。"])

    def test_allows_dictionary_term_repeated_with_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】前記流路は、それぞれよりも小さな絞り部を有し、前記絞り部の周囲には、冷却流路が形成されている装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_repeated_claim_term_lacks_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔は、前記アルミ箔を支持し、アルミ箔の端部を覆う装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(
            diagnostics[0].message,
            "請求項1の語句 アルミ箔 は、2回目以降または引用元の請求項で出現済みですが、前記・該・当該が付いていません（前記ぬけ）。",
        )

    def test_allows_repeated_claim_term_with_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔は、前記アルミ箔を支持し、当該アルミ箔の端部を覆う装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_claim_reference_at_end(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌器処理槽を備える装置。",
                    "【請求項2】前記流路部材が、酸化アルミニウムからなる、ことを特徴とする請求項1に記載のパルス殺菌器処理槽。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌器処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_claim_reference_at_start(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌器処理槽を備える装置。",
                    "【請求項2】請求項1に記載のパルス殺菌器処理槽において、前記流路部材が酸化アルミニウムからなる装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌器処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_multiple_claim_reference(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌器処理槽を備える装置。",
                    "【請求項2】請求項1に記載のパルス殺菌器処理槽。",
                    "【請求項3】請求項1または請求項2に記載のパルス殺菌器処理槽。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌器処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_claim_category_term_after_claim_reference_with_variant_phrases(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】パルス殺菌処理槽を備える装置。",
                    "【請求項2】請求項1に記載のパルス殺菌処理槽。",
                    "【請求項3】請求項1に記載するパルス殺菌処理槽。",
                    "【請求項4】請求項1に記載されたパルス殺菌処理槽。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                and "パルス殺菌処理槽" in diagnostic.message
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_dependent_claim_term_lacks_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔を備える装置。",
                    "【請求項2】請求項1に記載の装置であって、アルミ箔が樹脂層に接する装置。",
                ]
            )
        )

        messages = [
            diagnostic.message
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
        ]
        self.assertIn(
            "請求項2の語句 アルミ箔 は、2回目以降または引用元の請求項で出現済みですが、前記・該・当該が付いていません（前記ぬけ）。",
            messages,
        )

    def test_allows_dependent_claim_term_with_reference_prefix(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【請求項1】アルミ箔を備える装置。",
                    "【請求項2】請求項1に記載の装置であって、前記アルミ箔が樹脂層に接する装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "CLAIM_TERM_REFERENCE_PREFIX"
                for diagnostic in result.diagnostics
            )
        )


if __name__ == "__main__":
    unittest.main()
