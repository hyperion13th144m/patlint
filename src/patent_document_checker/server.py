from __future__ import annotations

import argparse
import multiprocessing
import threading
import webbrowser

import uvicorn

from patent_document_checker.api import app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main() -> None:
    multiprocessing.freeze_support()
    args = _parse_args()
    url = f"http://{args.host}:{args.port}{args.path}"

    if args.open:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patent Document Checker API server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port")
    parser.add_argument("--path", default="/ui", help="path to open in the browser")
    parser.add_argument("--reload", action="store_true", help="enable uvicorn auto reload")
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument(
        "--open",
        dest="open",
        action="store_true",
        default=True,
        help="open the API client UI in a browser after startup",
    )
    browser.add_argument(
        "--no-open",
        dest="open",
        action="store_false",
        help="do not open a browser",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
