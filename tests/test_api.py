from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from patent_document_checker.api import (
        TextCheckRequest,
        app,
        check_text_endpoint,
        help_page,
        ui,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local test env
    if exc.name != "fastapi":
        raise
    TextCheckRequest = None
    app = None
    check_text_endpoint = None
    help_page = None
    ui = None


@unittest.skipIf(ui is None, "fastapi is not installed")
class ApiTests(unittest.TestCase):
    def test_ui_is_served(self) -> None:
        response = ui()
        body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.media_type)
        self.assertIn("PatLint", body)
        self.assertIn("/api/check-text", body)
        self.assertIn("/api/check-docx", body)
        self.assertIn('href="/help"', body)
        self.assertIn('target="_blank"', body)
        self.assertIn("/ui/assets/favicon.ico", body)
        self.assertIn("/ui/assets/favicon.svg", body)
        self.assertIn("語句出現表", body)
        self.assertIn("符号の説明用一覧", body)
        claim_index = body.index("renderClaimRelationships(data.claims")
        reference_index = body.index("renderReferenceSigns(data.reference_sign_entries")
        term_index = body.index("renderTermOccurrences(data.term_occurrences")
        self.assertLess(claim_index, reference_index)
        self.assertLess(reference_index, term_index)

    def test_ui_assets_are_mounted(self) -> None:
        self.assertTrue(
            any(getattr(route, "path", None) == "/ui/assets" for route in app.routes)
        )

    def test_help_page_shows_default_word_files(self) -> None:
        response = help_page()
        body = response.body.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.media_type)
        self.assertIn("PatLint Help", body)
        self.assertIn("チェックルール概要", body)
        self.assertIn("FORBIDDEN_CHARACTER", body)
        self.assertIn("CLAIM_DEPENDENCY", body)
        self.assertIn("FIGURE_REFERENCE", body)
        self.assertIn("default.json", body)
        self.assertIn("default-terms.txt", body)
        self.assertIn("extra.txt", body)
        self.assertIn("claims_ng", body)
        self.assertIn("ねじ", body)
        self.assertIn("適宜", body)

    def test_help_route_is_registered(self) -> None:
        self.assertTrue(
            any(getattr(route, "path", None) == "/help" for route in app.routes)
        )

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
        self.assertIn("diagnostic_views", data)

    def test_check_text_endpoint_includes_diagnostic_views(self) -> None:
        data = check_text_endpoint(
            TextCheckRequest(
                text="\n".join([
                    "【書類名】明細書",
                    "【技術分野】",
                    "【０００１】本文",
                ]),
                source="api-test",
            )
        )

        views = data["diagnostic_views"]
        self.assertTrue(any(view["rule_label"] == "段落末尾句点" for view in views))
        self.assertTrue(any(view["location"] == "段落【0001】" for view in views))
        self.assertTrue(all("suggestion" not in view for view in views))


if __name__ == "__main__":
    unittest.main()
