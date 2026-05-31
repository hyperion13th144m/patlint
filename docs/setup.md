# セットアップと使い方

## コマンドライン版

### インストール方法

Python 3.11 以降を用意し、リポジトリを取得します。

```bash
git clone https://github.com/hyperion13th144m/patlint.git
cd patlint
uv sync
```

パッケージとしてインストールする場合は、配布元の手順に従って `patlint` をインストールしてください。

### CLI の使い方

```bash
uv run patlint path/to/document.docx
uv run patlint --text claims.txt --html report.html
```

ソースツリーから直接実行する場合は次のように実行できます。

```bash
PYTHONPATH=src python3 -m patent_document_checker.cli path/to/document.docx
PYTHONPATH=src python3 -m patent_document_checker.cli --text claims.txt --html report.html
```

### API サーバの起動方法

```bash
uv run patlint-api
uv run patlint-api --host 127.0.0.1 --port 8000 --no-open
```

ソースツリーから直接起動する場合は次のように実行できます。

```bash
PYTHONPATH=src python3 -m patent_document_checker.server --reload
```

### `/ui` にアクセスして使う

API サーバを起動したら、ブラウザで次の URL を開きます。

```text
http://127.0.0.1:8000/ui
```

画面から docx をアップロードするか、テキストを貼り付けて解析できます。

主な API エンドポイントは次のとおりです。

- `GET /health`
- `GET /ui`
- `GET /help`
- `POST /api/check-text`
- `POST /api/check-ooxml`
- `POST /api/check-docx`

## Windows 版

### インストール方法（ダウンロード）

[GitHub Releases](https://github.com/hyperion13th144m/patlint/releases) から patlint-api-windows.zip をダウンロードします。zip を展開すると、次のような構成になります。

```text
patlint-api.exe
manifest.xml
words/
  custom-sample.json
  custom-terms-sample.txt
```

`custom-sample.json` / `custom-terms-sample.txt` は見本ファイルです。ユーザー定義を追加する場合は、同じ `words` フォルダに以下の名前でコピーまたは作成します。

```text
words/custom.json
words/custom-terms.txt
```

### API サーバー起動

`patlint-api.exe` をダブルクリックすると、API サーバが `127.0.0.1:8000` で起動します。ブラウザで API クライアント画面を開きます。

```text
http://127.0.0.1:8000/ui
```

ブラウザを開きたくない場合は、コマンドラインから `--no-open` を付けて起動します。

```powershell
patlint-api.exe --no-open
```

### マニフェスト設置

Word アドインを使う場合は、zip に含まれる `manifest.xml` を Word に sideload します。Windows 版 Word では、manifest を置いたフォルダを共有フォルダー カタログとして登録します。

例:

```text
C:\PatLintAddin\manifest.xml
```

このフォルダを Windows の共有フォルダにし、共有パスを控えます。

```text
\\YOUR-PC-NAME\PatLintAddin
```

### Word Add-in 設定方法

1. `patlint-api.exe` を起動します。
2. Word を開きます。
3. `ファイル` → `オプション` → `トラスト センター` → `トラスト センターの設定` を開きます。
4. `信頼できるアドイン カタログ` を開きます。
5. `カタログ URL` に共有パスを追加します。
6. `メニューに表示する` にチェックします。
7. Word を再起動します。
8. `挿入` → `アドインを入手` または `個人用アドイン` を開きます。
9. `共有フォルダー` から `PatLint` を選択します。

アドインは Word 文書全体のプレーンテキストを取得し、ローカルの PatLint API (`http://127.0.0.1:8000/api/check-text`) に送信します。
