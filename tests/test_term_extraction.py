from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.parser import parse_text
from patent_document_checker.terms import (
    extract_claim_terms,
    extract_claim_terms_by_number,
    extract_document_terms_with_signs,
    extract_term_occurrences,
    extract_terms_with_signs,
)


class TermExtractionTests(unittest.TestCase):
    def test_extracts_ascii_katakana_iupac_and_kanji_terms(self) -> None:
        terms = extract_claim_terms(
            "前記CPUモジュールと、高速プロセッサと、"
            "2-メチル-1-プロパノールを含む制御装置。"
        )

        self.assertIn("CPUモジュール", terms)
        self.assertIn("高速プロセッサ", terms)
        self.assertIn("2-メチル-1-プロパノール", terms)
        self.assertIn("制御装置", terms)

    def test_extracts_prefixed_katakana_kanji_terms_as_whole_terms(self) -> None:
        terms = extract_claim_terms("前記パルス印加部とは別部材の配管に設けられる。")

        self.assertIn("パルス印加部", terms)
        self.assertNotIn("パルス", terms)
        self.assertNotIn("印加部", terms)

    def test_extracts_ordinal_prefixed_terms_as_whole_terms(self) -> None:
        terms = extract_claim_terms("第１電極と第２の電極を備える電池。")

        self.assertIn("第1電極", terms)
        self.assertIn("第2の電極", terms)
        self.assertNotIn("電極", terms)

    def test_normalizes_fullwidth_ascii_and_dash_variants(self) -> None:
        terms = extract_claim_terms("ＡＢＣ123信号と２−オクタノンを含む装置。")

        self.assertIn("ABC123", terms)
        self.assertIn("2-オクタノン", terms)

    def test_filters_common_claim_noise_terms(self) -> None:
        terms = extract_claim_terms("請求項1に記載の装置であって、前記装置は方法を実行する。")

        self.assertNotIn("記載", terms)
        self.assertNotIn("装置", terms)
        self.assertNotIn("方法", terms)

    def test_extracts_dictionary_stems_with_generated_suffixes(self) -> None:
        terms = extract_claim_terms(
            "ねじ部材、ねじ部、ねじ機構、ねじ手段、ねじ体、"
            "送り出し機構、送り出し手段、送り出し工程、送り出しステップを備える。"
        )

        self.assertIn("ねじ部材", terms)
        self.assertIn("ねじ部", terms)
        self.assertIn("ねじ機構", terms)
        self.assertIn("ねじ手段", terms)
        self.assertIn("ねじ体", terms)
        self.assertIn("送り出し機構", terms)
        self.assertIn("送り出し手段", terms)
        self.assertIn("送り出し工程", terms)
        self.assertIn("送り出しステップ", terms)

    def test_extracts_katakana_term_before_alphanumeric_sign(self) -> None:
        terms = extract_terms_with_signs("供給管４ｂとポンプ４ｄを具備する。", source="0029")

        self.assertEqual(
            [(item.whole_string, item.term, item.sign, item.source) for item in terms],
            [
                ("供給管4b", "供給管", "4b", "0029"),
                ("ポンプ4d", "ポンプ", "4d", "0029"),
            ],
        )

    def test_extracts_terms_with_numeric_and_alphanumeric_signs(self) -> None:
        terms = extract_terms_with_signs(
            "パルス印加部５と第１電極１０ａと第２電極Ａ－１と制御部Ａ’を備える。"
        )

        self.assertEqual(
            [(item.whole_string, item.term, item.sign) for item in terms],
            [
                ("パルス印加部5", "パルス印加部", "5"),
                ("第1電極10a", "第1電極", "10a"),
                ("第2電極A-1", "第2電極", "A-1"),
                ("制御部A'", "制御部", "A'"),
            ],
        )

    def test_removes_prefix_from_signed_term_whole_string(self) -> None:
        terms = extract_terms_with_signs("前記流路部材３０と前記流路１００と前記連通路１０３を備える。")

        self.assertEqual(
            [(item.whole_string, item.term, item.sign) for item in terms],
            [
                ("流路部材30", "流路部材", "30"),
                ("流路100", "流路", "100"),
                ("連通路103", "連通路", "103"),
            ],
        )

    def test_extracts_terms_with_signs_from_embodiments_and_abstract(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理槽３に設けられる。",
                    "【書類名】要約書",
                    "【要約】制御部Ａ２は処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】パルス印加部を備える装置。",
                ]
            )
        )

        self.assertEqual(
            [
                (item.term, item.sign, item.source)
                for item in extract_document_terms_with_signs(document.tree)
            ],
            [
                ("パルス印加部", "5", "0001"),
                ("処理槽", "3", "0001"),
                ("制御部", "A2", "要約書"),
            ],
        )

    def test_extracts_term_occurrences_with_signed_terms_including_signs(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明を実施するための形態】",
                    "【０００１】パルス印加部５は処理槽３に設けられる。",
                    "【０００２】パルス印加部５は別の処理を実行する。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】CPUモジュールとパルス印加部を備える装置。",
                ]
            )
        )

        self.assertEqual(
            extract_term_occurrences(document.claims, document.tree),
            {
                "CPUモジュール": ["請求項1"],
                "パルス印加部": ["請求項1"],
                "パルス印加部5": ["0001", "0002"],
                "処理槽3": ["0001"],
            },
        )

    def test_extracts_terms_by_claim_number(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【請求項1】CPUモジュールを備える制御装置。",
                    "【請求項2】請求項1に記載のねじ部材。",
                ]
            )
        )

        self.assertEqual(
            extract_claim_terms_by_number(document.claims),
            {1: ["CPUモジュール", "制御装置"], 2: ["ねじ部材"]},
        )


if __name__ == "__main__":
    unittest.main()
