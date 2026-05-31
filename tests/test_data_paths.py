from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.data_paths import find_data_dir, find_data_dirs


class DataPathTests(unittest.TestCase):
    def test_finds_data_dir_from_current_working_directory(self) -> None:
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_dir = root / "words"
            data_dir.mkdir()
            os.chdir(root)
            try:
                self.assertEqual(find_data_dir("words"), data_dir)
            finally:
                os.chdir(original_cwd)

    def test_finds_data_dir_from_anchor_parent(self) -> None:
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as cwddir:
            root = Path(tmpdir)
            data_dir = root / "units"
            module_dir = root / "src" / "pkg"
            data_dir.mkdir()
            module_dir.mkdir(parents=True)
            anchor = module_dir / "module.py"
            anchor.write_text("", encoding="utf-8")

            os.chdir(cwddir)
            try:
                self.assertEqual(find_data_dir("units", anchor=anchor), data_dir)
            finally:
                os.chdir(original_cwd)

    def test_finds_multiple_data_dirs_from_cwd_and_anchor(self) -> None:
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as cwdtmp, tempfile.TemporaryDirectory() as anchortmp:
            cwd_root = Path(cwdtmp)
            anchor_root = Path(anchortmp)
            cwd_words = cwd_root / "words"
            anchor_words = anchor_root / "words"
            module_dir = anchor_root / "pkg"
            cwd_words.mkdir()
            anchor_words.mkdir()
            module_dir.mkdir()
            anchor = module_dir / "module.py"
            anchor.write_text("", encoding="utf-8")

            os.chdir(cwd_root)
            try:
                self.assertEqual(find_data_dirs("words", anchor=anchor), (cwd_words, anchor_words))
                self.assertEqual(find_data_dir("words", anchor=anchor), cwd_words)
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
