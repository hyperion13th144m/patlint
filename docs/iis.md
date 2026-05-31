# IIS で HTTPS 終端する構成

PatLint API は HTTP のまま起動し、Windows Server の IIS で HTTPS 終端する構成です。Word アドインを LAN 内の複数 PC から使う場合に向いています。

## 構成

```text
クライアント PC / Word
  https://patlint.example.local/addin/taskpane.html
        ↓ HTTPS

Windows Server / IIS
  SSL 証明書
  URL Rewrite + Application Request Routing
        ↓ HTTP

PatLint API
  http://127.0.0.1:8000
```

IIS と PatLint API を同じ Windows Server で動かす場合、PatLint API は `127.0.0.1:8000` に閉じて起動できます。

## 前提

IIS に以下をインストールします。

- URL Rewrite
- Application Request Routing (ARR)

IIS の HTTPS サイトに設定する証明書も用意します。社内 CA、既存のサーバ証明書、または組織で信頼済みの証明書を使ってください。

管理者で実行する。
```powershell
New-SelfSignedCertificate -DnsName "patlint.example.local" -CertStoreLocation "cert:\LocalMachine\My"
```
patlint.example.local は運用するホストの名前に置き換えてください。

証明書のエクスポート
```powershell
$cert = Get-ChildItem -Path cert:\LocalMachine\My | Where-Object { $_.Subject -like "*patlint.example.local*" }
Export-Certificate -Cert $cert -FilePath "hostname-certificate.cer"
```
エクスポートした証明書をクライアント PC にインストールし、信頼されたルート証明機関に追加します。

## PatLint API を起動する

IIS と同じサーバで起動する場合:

```powershell
patlint-api.exe --host 127.0.0.1 --port 8000 --no-open
```

IIS と PatLint API が別サーバの場合は、IIS から到達できるアドレスで起動します。

```powershell
patlint-api.exe --host 0.0.0.0 --port 8000 --no-open
```

可能であれば、IIS と同じサーバで `127.0.0.1` に閉じる構成を推奨します。

## ARR の proxy を有効化する

1. IIS Manager を開きます。
2. サーバーノードを選択します。
3. `Application Request Routing Cache` を開きます。
4. 右側の `Server Proxy Settings...` をクリックします。
5. `Enable proxy` にチェックします。
6. `Apply` をクリックします。

この設定を行わないと、URL Rewrite の rewrite rule を作っても reverse proxy として動きません。

## IIS サイトを作成する

例:

- Site name: `PatLint`
- Physical path: `C:\inetpub\patlint`
- Binding:
  - Type: `https`
  - Host name: `patlint.example.local`
  - Port: `443`
  - SSL certificate: 用意した証明書

クライアント PC から以下の名前で IIS サーバへ到達できるよう、DNS または hosts を設定します。

```text
patlint.example.local
```

## URL Rewrite rule を作成する

IIS Manager で `PatLint` サイトを選択します。

1. `URL Rewrite` を開きます。
2. `Add Rule(s)...` をクリックします。
3. `Blank rule` を選択します。
4. Name に `ReverseProxyToPatLint` を入力します。
5. Match URL を以下のように設定します。
   - Requested URL: `Matches the Pattern`
   - Using: `Regular Expressions`
   - Pattern: `(.*)`
6. Action を以下のように設定します。
   - Action type: `Rewrite`
   - Rewrite URL: `http://127.0.0.1:8000/{R:1}`
   - `Append query string`: checked
   - `Stop processing of subsequent rules`: checked
7. `Apply` をクリックします。

PatLint API が別サーバの場合は、Rewrite URL を変更します。

```text
http://192.168.1.10:8000/{R:1}
```

## web.config 例

IIS サイトの physical path に `web.config` を置く場合の例です。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ReverseProxyToPatLint" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:8000/{R:1}" appendQueryString="true" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

## manifest の URL を変更する

Word アドインの `manifest.xml` は、`127.0.0.1` ではなく IIS の HTTPS URL を参照する必要があります。

例:

```xml
<SourceLocation DefaultValue="https://patlint.example.local/addin/taskpane.html" />
```

以下の URL も同じホストに揃えます。

```xml
<IconUrl DefaultValue="https://patlint.example.local/ui/assets/favicon_32.png" />
<HighResolutionIconUrl DefaultValue="https://patlint.example.local/ui/assets/favicon_128.png" />
<SupportUrl DefaultValue="https://patlint.example.local/help" />
```

`VersionOverrides` 内の URL も変更します。

```xml
<bt:Url id="Commands.Url" DefaultValue="https://patlint.example.local/addin/taskpane.html" />
<bt:Url id="Taskpane.Url" DefaultValue="https://patlint.example.local/addin/taskpane.html" />
<bt:Url id="GetStarted.LearnMoreUrl" DefaultValue="https://patlint.example.local/help" />
```

`AppDomains` にも HTTPS のホストを追加します。

```xml
<AppDomain>https://patlint.example.local</AppDomain>
```

## Word に manifest を設定する

LAN 共有フォルダに、IIS URL に書き換えた `manifest.xml` を置きます。

```text
\\FILESERVER\OfficeAddins\PatLint\manifest.xml
```

各クライアント PC の Word で、その共有フォルダを `信頼できるアドイン カタログ` に登録します。

## 動作確認

まず IIS サーバ上で PatLint API を確認します。

```text
http://127.0.0.1:8000/health
```

次にクライアント PC のブラウザで IIS 経由の URL を確認します。

```text
https://patlint.example.local/health
https://patlint.example.local/ui
https://patlint.example.local/addin/taskpane.html
```

最後に Word でアドインを開き、`接続確認` を押します。

アドイン側の API URL 既定値は `window.location.origin` から自動設定されるため、IIS 経由で読み込んだ場合は `https://patlint.example.local` が既定値になります。

## トラブルシュート

- `https://patlint.example.local/ui` が開けない場合は、DNS/hosts、IIS binding、証明書、ファイアウォールを確認します。
- `502` や `Bad Gateway` になる場合は、PatLint API が起動しているか、Rewrite URL が正しいかを確認します。
- Word にアドインが表示されない場合は、manifest の共有フォルダ設定と `メニューに表示する` のチェックを確認します。
- Word のタスクペインが空白になる場合は、manifest 内の `SourceLocation`、証明書の信頼状態、`/addin/taskpane.html` がブラウザで開けるかを確認します。
