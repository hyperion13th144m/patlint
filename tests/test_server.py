from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patent_document_checker.server import _parse_args


class ServerArgumentTests(unittest.TestCase):
    def test_default_open_path_is_ui(self) -> None:
        with patch.object(sys, "argv", ["patent-document-checker-api"]):
            args = _parse_args()

        self.assertEqual(args.path, "/ui")
        self.assertTrue(args.open)

    def test_open_path_can_be_overridden(self) -> None:
        with patch.object(sys, "argv", ["patent-document-checker-api", "--path", "/docs"]):
            args = _parse_args()

        self.assertEqual(args.path, "/docs")


if __name__ == "__main__":
    unittest.main()
