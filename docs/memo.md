# PatLint memo
## Run the API

Installed package:

```bash
patent-document-checker-api
patent-document-checker-api --host 127.0.0.1 --port 8000 --no-open
```

From source:

```bash
PYTHONPATH=src python3 -m patent_document_checker.server --reload
```

API クライアント画面:

```text
http://127.0.0.1:8000/ui
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

## Windows exe

Windows ユーザー向けには、GitHub Actions で API サーバ起動用 exe を作成できます。

- workflow: `.github/workflows/build-windows-exe.yml`
- 出力 artifact: `patent-checker-api-windows`
- exe 名: `patent-checker-api.exe`

GitHub の Actions タブから `Build Windows API exe` を手動実行するか、`v*` 形式のタグを push すると Windows runner 上で exe をビルドします。

```bash
git tag v0.1.0
git push origin v0.1.0
```

ローカルの Windows 環境で作る場合は、PowerShell で以下を実行します。

```powershell
scripts\build-windows-exe.ps1
```

作成された `dist\patent-checker-api.exe` をダブルクリックすると、API サーバを `127.0.0.1:8000` で起動し、ブラウザで API クライアント画面 `http://127.0.0.1:8000/ui` を開きます。ブラウザを開きたくない場合は、コマンドラインから `--no-open` を付けて起動します。

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
