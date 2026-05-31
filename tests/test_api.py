from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from patent_document_checker.api import TextCheckRequest, check_text_endpoint, ui
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local test env
    if exc.name != "fastapi":
        raise
    TextCheckRequest = None
    check_text_endpoint = None
    ui = None


@unittest.skipIf(ui is None, "fastapi is not installed")
class ApiTests(unittest.TestCase):
    def test_ui_is_served(self) -> None:
        response = ui()
        body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.media_type)
        self.assertIn("Patent Document Checker", body)
        self.assertIn("/api/check-text", body)
        self.assertIn("/api/check-docx", body)
        self.assertIn("語句出現表", body)
        self.assertIn("符号の説明用一覧", body)

    def test_check_text_endpoint(self) -> None:
        data = check_text_endpoint(
            TextCheckRequest(text="【請求項１】装置。", source="api-test")
        )

        self.assertEqual(data["source"], "api-test")
        self.assertIn("diagnostics", data)
        self.assertIn("term_occurrences", data)
        self.assertIn("claims", data)
        self.assertIn("unit_checks", data)
        self.assertIn("reference_sign_entries", data)


if __name__ == "__main__":
    unittest.main()
