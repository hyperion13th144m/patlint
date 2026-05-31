# PatLint

PatLint は、特許明細書・特許請求の範囲・要約書のテキストをチェックするツールです。docx またはテキストを入力し、診断結果、請求項の関係、符号の説明用一覧、語句出現表、単位チェックなどを確認できます。

## 概要

PatLint は、特許文書作成時のセルフチェックを補助するためのローカル実行型ツールです。コマンドライン、ローカル API サーバ、ブラウザ UI、Windows 版 exe、Microsoft Word アドインから利用できます。

詳しい説明は以下を参照してください。

- [チェックルール](docs/rules.md)
- [セットアップと使い方](docs/setup.md)
- [開発メモ](docs/development.md)

## 実行できるプラットフォーム

- Python 3.11 以降が動作する Windows / macOS / Linux
- Windows 版単体 exe
- Microsoft Word アドインは、Office Add-ins を sideload できる Word 環境

## ライセンス

MIT License です。詳細は [LICENSE](LICENSE) を参照してください。

## 免責

PatLint の診断結果は、特許出願書類の品質確認を補助するための参考情報です。法的判断、出願可否、権利範囲、拒絶理由の有無、特許庁提出形式への適合を保証するものではありません。実際の出願・補正・権利化判断は、専門家による確認を行ってください。
