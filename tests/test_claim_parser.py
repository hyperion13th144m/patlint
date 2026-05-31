from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.parser import extract_claim_references, parse_text


class ClaimParserTests(unittest.TestCase):
    def test_extracts_claims_with_fullwidth_numbers(self) -> None:
        document = parse_text("【特許請求の範囲】\n【請求項１】装置。\n【請求項２】請求項１に記載の装置。")

        self.assertEqual([claim.number for claim in document.claims], [1, 2])
        self.assertEqual(document.claims[1].referenced_claims, [1])

    def test_claims_track_official_multi_multi_states(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【請求項1】装置。",
                    "【請求項2】装置。",
                    "【請求項3】請求項1又は2に記載の装置。",
                    "【請求項4】請求項2又は3に記載の装置。",
                    "【請求項5】請求項4に記載の装置。",
                    "【請求項6】請求項5に記載の装置。",
                ]
            )
        )

        states = {
            claim.number: (
                claim.is_multiple_dependent,
                claim.references_multiple_dependent,
                claim.is_multi_multi,
                claim.references_multi_multi,
            )
            for claim in document.claims
        }
        self.assertEqual(states[3], (True, False, False, False))
        self.assertEqual(states[4], (True, True, True, False))
        self.assertEqual(states[5], (False, True, False, True))
        self.assertEqual(states[6], (False, True, False, True))

    def test_extract_claim_references_supports_ranges(self) -> None:
        self.assertEqual(extract_claim_references("請求項１〜３のいずれかに記載の装置。"), [1, 2, 3])
        self.assertEqual(extract_claim_references("請求項4から2のいずれかに記載の装置。"), [4, 3, 2])

    def test_extract_claim_references_supports_omitted_claim_prefixes(self) -> None:
        self.assertEqual(extract_claim_references("請求項１、２、４に記載の装置。"), [1, 2, 4])
        self.assertEqual(extract_claim_references("請求項１を引用する請求項３に記載の装置。"), [1, 3])
        self.assertEqual(extract_claim_references("請求項１を引用する請求項４、６～８に記載の装置。"), [1, 4, 6, 7, 8])


if __name__ == "__main__":
    unittest.main()
