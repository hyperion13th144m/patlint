from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import check_docx_bytes, check_text
from .report import render_html_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Patent Document Checker MVP")
    parser.add_argument("path", nargs="?", help=".docx file to check")
    parser.add_argument("--text", help="plain text file to check")
    parser.add_argument("--html", help="write an HTML report")
    args = parser.parse_args()

    if args.text:
        result = check_text(Path(args.text).read_text(encoding="utf-8"), source=args.text)
    elif args.path:
        path = Path(args.path)
        result = check_docx_bytes(path.read_bytes(), source=str(path))
    else:
        parser.error("provide a .docx path or --text")

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    if args.html:
        Path(args.html).write_text(render_html_report(result), encoding="utf-8")


if __name__ == "__main__":
    main()
