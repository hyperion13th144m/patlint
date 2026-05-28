# Patent Checker

Patent Document Checker MVP v0.1 implementation based on `docs/design.md`.

## Run the API

```bash
python3 -m uvicorn patent_document_checker.api:app --app-dir src --reload
```

Endpoints:

- `GET /health`
- `POST /api/check-text`
- `POST /api/check-ooxml`
- `POST /api/check-docx`

## Run the CLI

```bash
PYTHONPATH=src python3 -m patent_document_checker.cli path/to/document.docx
PYTHONPATH=src python3 -m patent_document_checker.cli --text claims.txt --html report.html
```

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
