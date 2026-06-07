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

IIS で HTTPS 終端して LAN 内から利用する構成は [IIS で HTTPS 終端する構成](iis.md) を参照してください。

## VSTO 版 Word アドイン

JavaScript サイドロード版と同等の機能を持つ VSTO 版アドインです。
診断結果の各項目に「移動」ボタンがあり、クリックすると Word 文書内の該当箇所にジャンプします。

### 必要環境

- Windows
- Microsoft Word 2016 以降
- .NET Framework 4.7 以上（Word と同じ PC にインストール済みであることが多い）
- Visual Studio 2019/2022（**Office/SharePoint 開発**ワークロード）※ビルドする場合のみ

### ビルド方法

リポジトリを取得し、Visual Studio でソリューションを開いてビルドします。

```bash
git clone https://github.com/hyperion13th144m/patlint.git
```

Visual Studio で `office-addin-vsto/PatlintAddin/PatlintAddin.sln` を開き、**ビルド → ソリューションのビルド** を実行します。

> **注意**: リポジトリには署名用の `.pfx` ファイルは含まれていません。
> 初回ビルド時に Visual Studio が自動で一時キー (`PatlintAddin_TemporaryKey.pfx`) を生成します。

### インストール方法（ビルド後）

#### 開発PC（自分でビルドした場合）

`bin/Debug/PatlintAddin.vsto` をダブルクリックするとインストールされます。

#### 別のPCに配布する場合

1. **証明書のエクスポート**  
   Visual Studio → プロジェクトのプロパティ → **署名** タブで、`PatlintAddin_TemporaryKey.pfx` を確認します。このファイルを配布先PCに渡します（git には含めないこと）。

2. **配布先PCで証明書をインポート**（管理者 PowerShell）

   ```powershell
   $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2("PatlintAddin_TemporaryKey.pfx")

   $store = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root","LocalMachine")
   $store.Open("ReadWrite"); $store.Add($cert); $store.Close()

   $store2 = New-Object System.Security.Cryptography.X509Certificates.X509Store("TrustedPublisher","LocalMachine")
   $store2.Open("ReadWrite"); $store2.Add($cert); $store2.Close()
   ```

3. `PatlintAddin.vsto` をダブルクリックしてインストールします。

### 使い方

1. `patlint-api.exe`（または `uv run patlint-api`）で API サーバを起動します。
2. Word を起動すると、リボンの **ホーム** タブに **PatLint** グループが表示されます。
3. **PatLint** ボタンをクリックするとタスクパネルが開きます。
4. **API URL** 欄にサーバのアドレスを入力し、**保存** をクリックします（次回以降は自動で読み込まれます）。
5. **文書をチェック** ボタンをクリックすると解析が実行されます。
6. 診断結果の **移動** ボタンをクリックすると、文書内の該当箇所にジャンプします。
