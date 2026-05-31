# Patent Checker

Patent Document Checker MVP v0.1 implementation based on `docs/design.md`.

## チェックルール概要

本ツールは、特許明細書・特許請求の範囲・要約書のテキストから、以下の観点で診断を出力します。

### 文字・語句

- `FORBIDDEN_CHARACTER`: JIS X 0208:1997 準拠の Shift_JIS に変換できない文字、丸付数字、半角カナ、合成用丸、ASCII 制御文字を error として検出します。
- `RECOMMENDED_WORDING_*`: `words/default.json`, `words/extra.txt`, `words/patterns.py` などの語句・正規表現に基づき、推奨されない語句や明らかな誤記を warning として検出します。カテゴリは `claims_ng`, `spec_pl`, `spec_antimonopoly`, `spec_trademark`, `typo_words`, `typo_regex` です。

### 請求項

- `CLAIM_NUMBERING`: 請求項番号の欠落、重複、0 以下の番号、請求項なしを検出します。
- `CLAIM_DEPENDENCY`: 存在しない請求項の引用、自己引用、後続請求項の引用を error として検出します。
- `MULTI_MULTI_CLAIM`: マルチマルチクレーム、またはマルチマルチクレームを引用する請求項を warning として検出します。
- `CLAIM_TERM_REFERENCE_PREFIX`: 請求項中で既出または引用元請求項に出現済みの語句に、前記・該・当該が付いていない可能性を warning として検出します。
- `DEPENDENT_CLAIM_INVENTION_NAME_MISMATCH`: 従属請求項末尾の発明の名称が、参照元請求項の発明の名称と一致しない場合に error とします。
- HTML レポートでは、請求項ごとの従属先・被従属・独立項/従属項/複数従属項の関係表も出力します。

### 明細書・要約書

- `PARAGRAPH_NUMBERING`: 段落番号が連続していない場合に error とします。
- `PARAGRAPH_END_PUNCTUATION`: 段落末尾が全角句点「。」で終わっていない場合に error とします。
- `ABSTRACT_LENGTH`: 要約書の文字数が 400 文字を超える場合に error とします。
- `LONG_EMBODIMENT_SENTENCE`: 実施形態の段落で、「。」または「．」で区切った一文が 200 文字以上の場合に warning とします。
- `MISSING_SUBJECT_IN_EMBODIMENT_SENTENCE`: 実施形態の文に「は」「が」「も」が含まれない場合、主語が欠けている可能性として warning とします。

### 発明の名称・請求項カテゴリ

- `INVENTION_TITLE_CLAIM_MISMATCH`: 発明の名称タグを「、」「，」「及び」「並びに」「および」「ならびに」で分割した語句と、独立請求項末尾の語句が完全一致しない場合に error とします。
- `CLAIM_TERM_IN_EMBODIMENTS`: 請求項から抽出した語句が、発明を実施するための形態に記載されていない場合に warning とします。
- `CLAIM_TERM_IN_TECH_SOLUTION`: 請求項から抽出した語句が、課題を解決するための手段に記載されていない場合に warning とします。

### 符号・図面

- `TERM_VARIATION`: 語句の先頭または末尾が近い表記揺れ候補を warning として検出します。
- `TERM_SIGN_CONFLICT`: 同じ語句に複数の符号が付いている場合に warning とします。
- `SIGN_TERM_CONFLICT`: 同じ符号に複数の語句が付いている場合に warning とします。
- `FIGURE_REFERENCE`: 図面の簡単な説明にある図番号が本文で言及されていない場合、または本文で言及された図番号が図面の簡単な説明にない場合に warning とします。「図1から図4」「図1～図5」「図1～5」の範囲表現も展開します。
- HTML レポートでは、符号付き語句一覧を、明細書の符号の説明へ貼り付けやすい形式で出力できます。連結記号、区切り文字、符号の全角/半角、ソート有無を切り替えられます。

### 単位

- 数値 + 単位表現を抽出し、`units/si_units.json`, `units/non_si_units.json`, `units/custom_units.json` に基づいて SI 単位、非 SI 単位、未知単位を HTML レポートに出力します。
- 非 SI 単位や非推奨略記は、設定ファイルに記載された `INFO` / `WARNING` とメッセージで表示します。

## カスタムデータ

`words/custom-sample.json` と `words/custom-terms-sample.txt` はサンプルです。ユーザーごとの追加設定は、以下のファイルを作成して記載します。

```text
words/custom.json
words/custom-terms.txt
```

これらの `custom` 実ファイルは `.gitignore` 対象です。`git pull` でローカル編集が上書きされないように、リポジトリには sample ファイルだけを含めます。

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

作成された `dist\patent-checker-api.exe` をダブルクリックすると、API サーバを `127.0.0.1:8000` で起動し、ブラウザで `/docs` を開きます。API クライアント画面は `http://127.0.0.1:8000/ui` です。ブラウザを開きたくない場合は、コマンドラインから `--no-open` を付けて起動します。

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
