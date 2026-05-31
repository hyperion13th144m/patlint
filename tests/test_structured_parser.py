from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.parser import RawBlock, parse_text
from patent_document_checker.structured_parser import parse_blocks_to_tree


class StructuredParserTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
