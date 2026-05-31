from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.parser import RawBlock
from patent_document_checker.units import extract_unit_checks_from_blocks


class UnitExtractionTests(unittest.TestCase):
    def test_extracts_si_non_si_unknown_and_fullwidth_units(self) -> None:
        results = extract_unit_checks_from_blocks(
            [
                RawBlock(
                    id="b0",
                    index=0,
                    text="圧力は１．２ａｔｍであり、長さは10 mm、温度は25℃、量は3.5fooである。",
                )
            ]
        )

        self.assertEqual(
            [item.to_dict() for item in results],
            [
                {
                    "line": 1,
                    "col": 4,
                    "matched": "１．２ａｔｍ",
                    "number": "1.2",
                    "unit": "atm",
                    "level": "WARNING",
                    "message": "非SI（気圧）：kPa または MPa を推奨",
                },
                {
                    "line": 1,
                    "col": 17,
                    "matched": "10 mm",
                    "number": "10",
                    "unit": "mm",
                    "level": "INFO",
                    "message": "SI単位またはSI併用単位です",
                },
                {
                    "line": 1,
                    "col": 26,
                    "matched": "25℃",
                    "number": "25",
                    "unit": "℃",
                    "level": "INFO",
                    "message": "SI併用可（摂氏）：K がSI基本単位",
                },
                {
                    "line": 1,
                    "col": 32,
                    "matched": "3.5foo",
                    "number": "3.5",
                    "unit": "foo",
                    "level": "INFO",
                    "message": "UNKNOWN：単位リストにない単位です",
                },
            ],
        )

    def test_extracts_ranges_percentages_and_fractions(self) -> None:
        results = extract_unit_checks_from_blocks(
            [
                RawBlock(
                    id="b2",
                    index=2,
                    text="範囲は10～20mm、割合は１０％以上２０％以下、分数は1/2 molである。",
                )
            ]
        )

        self.assertEqual(
            [(item.line, item.col, item.matched, item.number, item.unit) for item in results],
            [
                (3, 4, "10～20mm", "10~20", "mm"),
                (3, 15, "１０％", "10", "%"),
                (3, 20, "２０％", "20", "%"),
                (3, 29, "1/2 mol", "1/2", "mol"),
            ],
        )

    def test_avoids_unit_partial_matches_inside_words(self) -> None:
        results = extract_unit_checks_from_blocks(
            [RawBlock(id="b0", index=0, text="値は10inchと20inであり、30insideではない。")]
        )

        self.assertEqual(
            [(item.matched, item.unit, item.message) for item in results],
            [
                ("10inch", "inch", "非SI（インチ）：mm または cm を推奨"),
                ("20in", "in", "非SI（インチ）：mm または cm を推奨"),
                ("30inside", "inside", "UNKNOWN：単位リストにない単位です"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
