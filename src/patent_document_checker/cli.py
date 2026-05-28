from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import check_docx_bytes, check_text
from .parser import PatentDocumentIR, parse_docx_bytes, parse_text
from .report import render_html_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Patent Document Checker MVP")
    parser.add_argument("path", nargs="?", help=".docx file to check")
    parser.add_argument("--text", help="plain text file to check")
    parser.add_argument("--html", help="write an HTML report")
    parser.add_argument("--dump-tree", action="store_true", help="dump the parsed tag tree instead of diagnostics")
    args = parser.parse_args()

    document = _load_document(args, parser)

    if args.dump_tree:
        if document.tree is None:
            parser.error("parsed document tree is not available")
        print(json.dumps(document.tree.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.text:
        result = check_text(Path(args.text).read_text(encoding="utf-8"), source=args.text)
    else:
        path = Path(args.path)
        result = check_docx_bytes(path.read_bytes(), source=str(path))

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    if args.html:
        Path(args.html).write_text(render_html_report(result), encoding="utf-8")


def _load_document(args: argparse.Namespace, parser: argparse.ArgumentParser) -> PatentDocumentIR:
    if args.text:
        path = Path(args.text)
        return parse_text(path.read_text(encoding="utf-8"), source=str(path))
    if args.path:
        path = Path(args.path)
        return parse_docx_bytes(path.read_bytes(), source=str(path))
    parser.error("provide a .docx path or --text")
    raise AssertionError("unreachable")


if __name__ == "__main__":
    main()
