# 開発メモ

## 開発環境

```bash
uv sync
uv run python -m unittest discover -s tests
```

exe ビルドを再現する場合は、PyInstaller を含む extra を同期します。

```bash
uv sync --extra exe
```

## API サーバの開発起動

```bash
uv run patlint-api --reload
```

または、ソースツリーから直接起動します。

```bash
PYTHONPATH=src python3 -m patent_document_checker.server --reload
```

## wheel / sdist ビルド

```bash
uv build
```

## Windows exe ビルド

Windows では次を実行します。

```powershell
scripts\build-windows-exe.ps1
```

ローカルで PyInstaller を直接実行する場合は次のとおりです。

```bash
uv run pyinstaller --clean patlint-api.spec
```

生成物は `dist/` に出力されます。

## GitHub Actions

`Build Windows API exe` workflow はタグ `v*` の push または手動実行で Windows 版 exe をビルドします。artifact には次を含めます。

```text
patlint-api.exe
manifest.xml
words/
  custom-sample.json
  custom-terms-sample.txt
```

## バージョン更新とタグ

patch バージョンを上げる例です。

```bash
uv version --bump patch
git add pyproject.toml uv.lock
git commit -m "Bump version"
git tag vX.Y.Z
git push origin vX.Y.Z
```

## Word アドイン

Word アドインのタスクペインは以下にあります。

```text
src/patent_document_checker/addin/
office-addin/manifest.xml
```

API サーバは `/addin/...` を静的配信します。manifest は `http://127.0.0.1:8000/addin/taskpane.html` を参照します。

## Word VSTO
VS Community 2022 でビルドする。
- PatlintAddin プロジェクトのプロパティ
- 公開
- 今すぐ公開

.\publish のsetup.exe等を配布する。
Github Release にアップロードする。


## TODO

- Word アドインの `manifest.xml` は現在 URL を手編集する運用です。IIS など環境別の HTTPS URL に合わせやすくするため、manifest 生成コマンドまたは manifest テンプレート化を検討します。
