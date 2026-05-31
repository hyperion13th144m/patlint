from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text


class RuleParagraphTests(unittest.TestCase):
    def test_reports_missing_paragraph_number_after_last_valid_number(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文。",
                    "【０００２】本文。",
                    "【０００４】本文。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "PARAGRAPH_NUMBERING"
        ]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(
            diagnostics[0].message,
            "段落番号は2まで正しく連番ですが、それ以降は連番ではありません。",
        )
        self.assertEqual(diagnostics[0].location.search_text, "【0004】")

    def test_errors_when_paragraph_does_not_end_with_fullwidth_period(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文",
                    "【０００２】本文．",
                    "【０００３】本文。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "PARAGRAPH_END_PUNCTUATION"
        ]

        self.assertEqual(len(diagnostics), 2)
        self.assertEqual([diagnostic.severity for diagnostic in diagnostics], ["error", "error"])
        self.assertEqual(
            [diagnostic.location.search_text for diagnostic in diagnostics],
            ["【0001】", "【0002】"],
        )
        self.assertEqual(
            diagnostics[0].message,
            "段落の末尾が句点「。」で終わっていません。",
        )

    def test_allows_paragraph_ending_with_fullwidth_period(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "PARAGRAPH_END_PUNCTUATION"
                for diagnostic in result.diagnostics
            )
        )

    def test_allows_sequential_paragraph_numbers(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文。",
                    "【０００２】本文。",
                    "【０００３】本文。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "PARAGRAPH_NUMBERING"
                for diagnostic in result.diagnostics
            )
        )

    def test_errors_when_abstract_exceeds_400_characters(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】要約書",
                    f"【要約】{'あ' * 401}",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "ABSTRACT_LENGTH"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "error")
        self.assertEqual(diagnostics[0].message, "要約書の文字数が400文字を超えています（401文字）。")
        self.assertEqual(diagnostics[0].location.section_type, "abstract")
        self.assertEqual(diagnostics[0].location.search_text, "【要約】")

    def test_allows_abstract_with_400_characters(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】要約書",
                    f"【要約】{'あ' * 400}",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "ABSTRACT_LENGTH"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_when_embodiment_sentence_may_lack_subject(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】制御部を備える。装置は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "MISSING_SUBJECT_IN_EMBODIMENT_SENTENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(diagnostics[0].message, "段落【0001】の文に主語が欠けている可能性があります。")
        self.assertEqual(diagnostics[0].location.search_text, "【0001】")

    def test_allows_embodiment_sentences_with_subject_particles(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】制御部は処理を実行する。装置が信号を出力する。部材も移動する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "MISSING_SUBJECT_IN_EMBODIMENT_SENTENCE"
                for diagnostic in result.diagnostics
            )
        )

    def test_ignores_missing_subject_sentences_outside_embodiments(self) -> None:
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【背景技術】",
                    "【０００１】制御部を備える。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "MISSING_SUBJECT_IN_EMBODIMENT_SENTENCE"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_for_long_sentence_in_embodiments(self) -> None:
        long_sentence = "あ" * 199 + "。"
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    f"【０００１】{long_sentence}",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "LONG_EMBODIMENT_SENTENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].severity, "warning")
        self.assertEqual(diagnostics[0].message, "実施形態の一文が長すぎます（200文字）。")
        self.assertEqual(diagnostics[0].location.search_text, "【0001】")

    def test_allows_short_sentences_and_ignores_non_embodiment_long_sentences(self) -> None:
        long_sentence = "あ" * 199 + "。"
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【背景技術】",
                    f"【０００１】{long_sentence}",
                    "【発明を実施するための形態】",
                    f"【０００２】{'い' * 198}。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        self.assertFalse(
            any(
                diagnostic.rule_id == "LONG_EMBODIMENT_SENTENCE"
                for diagnostic in result.diagnostics
            )
        )

    def test_warns_for_fullwidth_period_long_sentence_in_embodiments(self) -> None:
        long_sentence = "あ" * 199 + "．"
        result = check_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    f"【０００１】短文。{long_sentence}",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                ]
            )
        )

        diagnostics = [
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.rule_id == "LONG_EMBODIMENT_SENTENCE"
        ]

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].message, "実施形態の一文が長すぎます（200文字）。")


if __name__ == "__main__":
    unittest.main()
