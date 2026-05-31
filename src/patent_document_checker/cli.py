from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import check_docx_bytes, check_text
from .parser import parse_docx_bytes, parse_text
from .report import render_html_report
from .terms import (
    extract_claim_terms_by_number,
    extract_document_terms_with_signs,
    extract_term_occurrences,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Patent Document Checker MVP")
    parser.add_argument("path", nargs="?", help=".docx file to check")
    parser.add_argument("--text", help="plain text file to check")
    parser.add_argument("--html", help="write an HTML report")
    parser.add_argument("--debug", action="store_true", help="include debug details in the HTML report")
    args = parser.parse_args()

    term_occurrences = None
    terms_with_signs = None
    claims = None
    debug_terms_by_claim = None
    debug_terms_with_signs = None
    if args.text:
        path = Path(args.text)
        text = path.read_text(encoding="utf-8")
        result = check_text(text, source=args.text)
        if args.html:
            document = parse_text(text, source=args.text)
            claims = document.claims
            term_occurrences = extract_term_occurrences(document.claims, document.tree)
            terms_with_signs = extract_document_terms_with_signs(document.tree)
            if args.debug:
                debug_terms_by_claim = extract_claim_terms_by_number(document.claims)
                debug_terms_with_signs = terms_with_signs
    elif args.path:
        path = Path(args.path)
        docx_bytes = path.read_bytes()
        result = check_docx_bytes(docx_bytes, source=str(path))
        if args.html:
            document = parse_docx_bytes(docx_bytes, source=str(path))
            claims = document.claims
            term_occurrences = extract_term_occurrences(document.claims, document.tree)
            terms_with_signs = extract_document_terms_with_signs(document.tree)
            if args.debug:
                debug_terms_by_claim = extract_claim_terms_by_number(document.claims)
                debug_terms_with_signs = terms_with_signs
    else:
        parser.error("provide a .docx path or --text")

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    if args.html:
        Path(args.html).write_text(
            render_html_report(
                result,
                term_occurrences=term_occurrences,
                terms_with_signs=terms_with_signs,
                claims=claims,
                debug_terms_by_claim=debug_terms_by_claim,
                debug_terms_with_signs=debug_terms_with_signs,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
