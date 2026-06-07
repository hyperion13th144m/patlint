# PatlintAddin — VSTO版 Word アドイン

## 必要な環境

- Windows 10/11
- Visual Studio 2022（**Office/SharePoint 開発**ワークロードをインストール）
- .NET Framework 4.8
- Microsoft Word 2016 以降

## ビルド

1. `office-addin-vsto/PatlintAddin.csproj` を Visual Studio で開く
2. **ビルド → ソリューションのビルド**
3. 初回はNuGet パッケージが自動復元される

> Visual Studio のプロジェクトテンプレートで作成した場合は `ThisAddIn.cs` の `#region VSTO generated code` 内を
> テンプレートが自動生成したコードで置き換えてください。

## インストール（開発時サイドロード）
Visual Studio のデバッグ実行

または↓

```powershell
# 管理者権限の PowerShell で実行
$path = (Resolve-Path ".\bin\Debug\PatlintAddin.vsto").Path + "|vstolocal"
$regKey = "HKCU:\Software\Microsoft\Office\Word\Addins\PatlintAddin"
New-Item -Path $regKey -Force | Out-Null
Set-ItemProperty -Path $regKey -Name "Description" -Value "PatLint Word Addin"
Set-ItemProperty -Path $regKey -Name "FriendlyName" -Value "PatLint"
Set-ItemProperty -Path $regKey -Name "LoadBehavior" -Value 3 -Type DWord
Set-ItemProperty -Path $regKey -Name "Manifest" -Value "$path"
```

Word を再起動するとタスクウィンドウが表示されます。

## 配布（ClickOnce）

Visual Studio の **プロジェクト → 発行** から ClickOnce 発行ウィザードを使用します。
発行先として既存の IIS サーバー（`docs/iis.md` 参照）を利用できます。

## Word VSTO
VS Community 2022 でビルドする。
- PatlintAddin プロジェクトのプロパティ
- 公開
- 今すぐ公開

.\publish のsetup.exe等を配布する。
Github Release にアップロードする。

## 機能

| 機能 | 説明 |
|------|------|
| API URL設定 | テキストボックスに入力して「保存」 → `%APPDATA%` に永続保存 |
| API確認 | `/health` エンドポイントの疎通確認 |
| 文書をチェック | アクティブ文書のテキストをAPIに送信し結果を表示 |
| **移動ボタン** | 診断結果の各行に表示。クリックで該当箇所にジャンプ |

### ジャンプの動作順序

1. `search_text` がある場合 → Word の Find で文書内を検索してジャンプ
2. 見つからない場合または `search_text` がない場合 → `block_index`（段落番号）で直接ジャンプ
