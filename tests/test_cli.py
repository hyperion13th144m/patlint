from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_debug_html_includes_extracted_claim_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "claims.txt"
            output_path = Path(tmpdir) / "report.html"
            input_path.write_text(
                "【請求項1】CPUモジュールを備える制御装置。",
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "patent_document_checker.cli",
                    "--text",
                    str(input_path),
                    "--html",
                    str(output_path),
                    "--debug",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONPATH": "src"},
            )

            html = output_path.read_text(encoding="utf-8")

        self.assertIn("抽出語句一覧", html)
        self.assertIn("CPUモジュール", html)
        self.assertIn("制御装置", html)


if __name__ == "__main__":
    unittest.main()
