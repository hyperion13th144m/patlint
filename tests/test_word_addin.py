from __future__ import annotations

import sys
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from patent_document_checker.api import app
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local test env
    if exc.name != "fastapi":
        raise
    app = None


@unittest.skipIf(app is None, "fastapi is not installed")
class WordAddinTests(unittest.TestCase):
    def test_addin_static_route_is_mounted(self) -> None:
        self.assertTrue(any(getattr(route, "path", None) == "/addin" for route in app.routes))

    def test_taskpane_contains_office_js_and_patlint_api_call(self) -> None:
        taskpane = Path("src/patent_document_checker/addin/taskpane.html").read_text(
            encoding="utf-8"
        )
        script = Path("src/patent_document_checker/addin/taskpane.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("office.js", taskpane)
        self.assertIn('<input id="api-url" type="url">', taskpane)
        self.assertNotIn("127.0.0.1:8000", taskpane)
        self.assertIn("Word.run", script)
        self.assertIn("window.location.origin", script)
        self.assertIn("/api/check-text", script)
        self.assertIn("document.body", script)

    def test_manifest_points_to_local_taskpane(self) -> None:
        manifest = Path("office-addin/manifest.xml")
        root = ET.parse(manifest).getroot()
        xml_text = manifest.read_text(encoding="utf-8")

        self.assertTrue(root.tag.endswith("OfficeApp"))
        self.assertIn("http://127.0.0.1:8000/addin/taskpane.html", xml_text)
        self.assertIn("http://127.0.0.1:8000/help", xml_text)
        self.assertIn("ReadDocument", xml_text)


if __name__ == "__main__":
    unittest.main()
