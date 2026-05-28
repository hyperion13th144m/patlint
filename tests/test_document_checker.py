from __future__ import annotations

import unittest
from pathlib import Path
import sys
import os
import subprocess
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.engine import check_text
from patent_document_checker.parser import RawBlock, extract_claim_references, parse_text
from patent_document_checker.structured_parser import parse_blocks_to_tree


class DocumentCheckerTests(unittest.TestCase):
    def test_extracts_claims_with_fullwidth_numbers(self) -> None:
        document = parse_text("【特許請求の範囲】\n【請求項１】装置。\n【請求項２】請求項１に記載の装置。")

        self.assertEqual([claim.number for claim in document.claims], [1, 2])
        self.assertEqual(document.claims[1].referenced_claims, [1])

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

    def test_extract_claim_references_supports_ranges(self) -> None:
        self.assertEqual(extract_claim_references("請求項１〜３のいずれかに記載の装置。"), [1, 2, 3])
        self.assertEqual(extract_claim_references("請求項4から2のいずれかに記載の装置。"), [4, 3, 2])

    def test_builds_tagged_document_tree(self) -> None:
        document = parse_text(
            "\n".join(
                [
                    "【書類名】明細書",
                    "【発明の名称】ハンドスキャナ",
                    "【技術分野】",
                    "【０００１】",
                    "本発明は、走査位置の観測確認が容易なハンドスキャナに関する。",
                    "【図面の簡単な説明】",
                    "【０００２】",
                    "【図１】ハンドスキャナの説明図である。",
                    "【書類名】特許請求の範囲",
                    "【請求項１】装置。",
                    "【請求項２】請求項１に記載の装置。",
                ]
            )
        )

        tree = document.tree
        self.assertIsNotNone(tree)
        documents = tree.find_all(kind="document")
        self.assertEqual([node.text for node in documents], ["明細書", "特許請求の範囲"])
        spec = documents[0]
        self.assertEqual(spec.children[0].tag_name, "発明の名称")
        self.assertEqual(spec.children[1].children[0].tag_name, "0001")
        claim_doc = documents[1]
        self.assertEqual([node.number for node in claim_doc.find_all(kind="claim")], [1, 2])

    def test_tree_handles_multiple_tags_on_one_line(self) -> None:
        tree = parse_blocks_to_tree([RawBlock(id="b0", index=0, text="【００１１】【図１】説明図。【図２】別の説明図。")])

        paragraph = tree.find_all(kind="paragraph")[0]
        figures = paragraph.find_all(kind="figure")
        self.assertEqual([figure.number for figure in figures], [1, 2])
        self.assertEqual(figures[0].text, "説明図。")

    def test_cli_dump_tree_outputs_tree_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "sample.txt"
            input_path.write_text("【書類名】明細書\n【技術分野】\n【０００１】本文。", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "patent_document_checker.cli",
                    "--text",
                    str(input_path),
                    "--dump-tree",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONPATH": "src"},
            )

        self.assertIn('"kind": "root"', completed.stdout)
        self.assertIn('"tagName": "書類名"', completed.stdout)
        self.assertIn('"tagName": "0001"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
