from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.parser import parse_text
from patent_document_checker.terms import (
    extract_claim_terms,
    extract_claim_terms_by_number,
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

    def test_extracts_dictionary_terms_containing_hiragana(self) -> None:
        terms = extract_claim_terms("ねじ部材と送り出し機構を備える固定具。")

        self.assertIn("ねじ部材", terms)
        self.assertIn("送り出し機構", terms)

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
