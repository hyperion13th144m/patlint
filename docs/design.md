# Codexハンドオフ：Patent Checker Suite 構想とMVP実装方針

## 目的

特許書類および特許図面をチェックするためのツール群を開発する。

ただし、最初から1つの巨大アプリとして作らない。
以下の2つを **別プロダクト** として開発する。

```text
1. Patent Document Checker
   - Word/docx形式の特許書類をチェックする

2. Patent Drawing Checker
   - jpg/png/gif等の特許図面画像をチェックする
```

将来的には、両者を統合して **Patent Checker Suite** として扱えるようにする。
そのため、診断結果、符号モデル、設定、レポート形式などは、最初から共通化を意識して設計する。

---

# 全体方針

## プロダクト分離

```text
Patent Checker Suite
  ├─ Patent Document Checker
  │    ├─ docx解析
  │    ├─ 請求項チェック
  │    ├─ 前記チェック
  │    ├─ 明細書サポートチェック
  │    └─ 明細書中の符号抽出
  │
  ├─ Patent Drawing Checker
  │    ├─ 図面画像OCR
  │    ├─ 図中符号抽出
  │    ├─ OCR結果の確認・修正
  │    └─ 明細書符号との照合
  │
  └─ Patent Checker Common
       ├─ Diagnostics JSON
       ├─ ReferenceSign model
       ├─ Report schema
       ├─ Rule schema
       └─ 共通設定
```

## 重要な設計原則

1. Document Checker と Drawing Checker は別プロダクトとして開発する。
2. ただし、将来統合できるように共通スキーマを設計する。
3. UI、API、Core Engineを分離する。
4. Wordアドインに重い処理を入れない。
5. 図面OCR処理はDocument Checkerに混ぜない。
6. 診断結果は共通のDiagnostics JSON形式で返す。
7. 未公開特許文書・図面を扱うため、本文や画像内容をログに出さない。

---

# プロダクト1：Patent Document Checker

## 目的

Word `.docx` 形式で作成された特許書類を解析し、形式的・半形式的な不備をチェックする。

対象：

```text
- 明細書
- 特許請求の範囲
- 要約書
- 図面の簡単な説明
- 符号の説明
```

## 主なチェック項目

MVP：

```text
- 請求項番号が連続しているか
- 請求項番号に欠番・重複がないか
- 請求項の引用先が存在するか
- 自己引用していないか
- 後続請求項を引用していないか
- マルチマルチクレームであるか
```

将来：

```text
- 前記漏れ
- 請求項文言が明細書で使われているか
- 明細書サポート
- 符号チェック
- 用語揺れ
- 必須セクションの有無
- docxコメント挿入
- Wordアドイン連携
```

## 基本アーキテクチャ

```text
docx / OOXML
  ↓
Document Parser
  ↓
PatentDocumentIR
  ↓
Document Rule Engine
  ↓
Diagnostics JSON
  ↓
Desktop UI / Word Add-in / HTML Report
```

---

# プロダクト2：Patent Drawing Checker

## 目的

特許図面画像から英数字の符号を抽出し、明細書側で使用されている符号と照合する。

作製時の図面ファイルは以下を想定する。

```text
- jpg
- jpeg
- png
- gif
```

将来的には以下も検討する。

```text
- tif
- tiff
- pdf
- docx内に埋め込まれた図面画像
```

## 主なチェック項目

MVP：

```text
- 画像ファイルから英数字をOCR抽出する
- OCR結果をbbox付きで保持する
- 数字・英数字らしい候補だけを抽出する
- 検出結果をJSONで出力する
- 画像上に検出枠を表示する
```

次段階：

```text
- 複数画像フォルダを一括処理する
- 図番をファイル名から推定する
- 明細書側の符号リストJSONと照合する
- 図面にあるが明細書にない符号を警告する
- 明細書にあるが図面にない符号を警告する
- OCR誤認識候補を提示する
```

将来：

```text
- docxを入力して明細書側符号を抽出する
- 図面画像フォルダとdocxをセットでチェックする
- OCR結果を手動修正する
- 誤検出を無視リストに登録する
- 検出枠付きHTMLレポートを出力する
```

## 基本アーキテクチャ

```text
jpg/png/gif
  ↓
Image Preprocessor
  ↓
OCR Engine
  ↓
Drawing Sign Extractor
  ↓
DrawingSign list
  ↓
Sign Compare Engine
  ↓
Diagnostics JSON
  ↓
Drawing UI / HTML Report
```

---

# Common設計

両プロダクトで将来共通化するため、以下は共通スキーマとして設計する。

```text
packages/common/
  schemas/
  models/
  diagnostics/
  reference_signs/
```

または、最初は別リポジトリにしても、同じJSONスキーマを使う。

---

## 共通モデル：Diagnostic

```python
class Diagnostic(BaseModel):
    rule_id: str
    severity: Literal["error", "warning", "info"]
    message: str
    location: DiagnosticLocation | None = None
    suggestion: str | None = None
```

## 共通モデル：DiagnosticLocation

```python
class DiagnosticLocation(BaseModel):
    source_type: Literal["document", "drawing", "common"] | None = None

    # document location
    section_type: str | None = None
    claim_number: int | None = None
    block_id: str | None = None
    block_index: int | None = None
    search_text: str | None = None

    # drawing location
    figure_id: str | None = None
    image_file: str | None = None
    bbox: BoundingBox | None = None
```

## 共通モデル：BoundingBox

```python
class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
```

## 共通モデル：ReferenceSign

明細書側の符号。

```python
class ReferenceSign(BaseModel):
    sign: str
    label: str | None = None
    source: Literal["description", "claims", "abstract", "unknown"] = "unknown"
    locations: list[ReferenceSignLocation] = []
```

## 共通モデル：ReferenceSignLocation

```python
class ReferenceSignLocation(BaseModel):
    section_type: str | None = None
    paragraph_index: int | None = None
    claim_number: int | None = None
    text_snippet: str | None = None
```

## 共通モデル：DrawingSign

図面側の符号。

```python
class DrawingSign(BaseModel):
    sign: str
    raw_text: str
    normalized_sign: str
    confidence: float | None = None
    figure_id: str | None = None
    image_file: str | None = None
    bbox: BoundingBox | None = None
```

## 共通モデル：SignCompareResult

```python
class SignCompareResult(BaseModel):
    spec_signs: list[ReferenceSign] = []
    drawing_signs: list[DrawingSign] = []
    diagnostics: list[Diagnostic] = []
```

---

# Diagnostics JSON設計

Document CheckerもDrawing Checkerも同じ形式で返す。

```json
{
  "source": "sample.docx",
  "product": "document-checker",
  "diagnostics": [
    {
      "rule_id": "CLAIM_NUMBER_MISSING",
      "severity": "error",
      "message": "請求項2が欠落しています。",
      "location": {
        "source_type": "document",
        "section_type": "claims",
        "claim_number": 3,
        "search_text": "【請求項３】"
      },
      "suggestion": "請求項番号を確認してください。"
    }
  ],
  "summary": {
    "error": 1,
    "warning": 0,
    "info": 0
  }
}
```

Drawing Checkerの場合：

```json
{
  "source": "fig1.png",
  "product": "drawing-checker",
  "diagnostics": [
    {
      "rule_id": "DRAWING_SIGN_NOT_IN_SPEC",
      "severity": "warning",
      "message": "図1に符号「12」がありますが、明細書中に対応する符号が見つかりません。",
      "location": {
        "source_type": "drawing",
        "figure_id": "fig-1",
        "image_file": "fig1.png",
        "bbox": {
          "x": 120,
          "y": 80,
          "width": 32,
          "height": 18
        }
      },
      "suggestion": "符号12の説明を明細書に追加するか、図面の符号を確認してください。"
    }
  ],
  "summary": {
    "error": 0,
    "warning": 1,
    "info": 0
  }
}
```

---

# リポジトリ構成案

## 案A：モノレポ

将来統合を強く意識するならこちら。

```text
patent-checker-suite/
  apps/
    document-api/
    document-desktop/
    document-word-addin/
    drawing-api/
    drawing-desktop/
  packages/
    document-core/
    drawing-core/
    common/
  tests/
    document/
    drawing/
    common/
  docs/
    architecture/
    install/
```

メリット：

```text
- 共通モデルを共有しやすい
- Diagnostics JSONを統一しやすい
- 将来Suite化しやすい
```

デメリット：

```text
- 初期からリポジトリが大きく見える
- Codex実装が散らかる可能性がある
```

## 案B：別リポジトリ

別プロダクト感を強めるならこちら。

```text
patent-doc-checker/
patent-drawing-checker/
patent-check-common/
```

メリット：

```text
- 各プロダクトが独立して進めやすい
- MVPを切りやすい
- 図面OCR側の依存関係をDocument Checkerに混ぜずに済む
```

デメリット：

```text
- 共通スキーマの同期が必要
- 将来のSuite化で統合設計が必要
```

## 推奨

初期は **案B：別リポジトリ** を推奨する。

理由：

```text
- Document CheckerとDrawing Checkerは技術領域が違う
- OCR依存関係をdocxチェッカーに混ぜたくない
- それぞれMVPを独立して作れる
```

ただし、最初から `patent-check-common` のスキーマを意識する。

---

# Patent Document Checker ハンドオフ

## 目的

Word `.docx` の特許書類を解析し、請求項を中心にチェックする。

## MVP v0.1

実装対象：

```text
- docx読み込み
- word/document.xml解析
- RawBlock生成
- 特許タグ検出
- PatentDocumentIR生成
- 請求項抽出
- 請求項番号チェック
- 請求項引用関係チェック
- マルチマルチチェック
- Diagnostics JSON出力
- HTMLレポート
- FastAPI API
```

## API

```text
GET  /health
POST /api/check-text
POST /api/check-docx
POST /api/check-ooxml
```

## Rule

```text
CLAIM_NUMBERING
CLAIM_DEPENDENCY
MULTI_MULTI_CLAIM
```

## 将来実装

```text
- 明細書中の符号抽出
- ReferenceSign JSON出力
- 前記漏れ
- 明細書サポート
- Word Add-in
- Electron/Tauri UI
```

---

# Patent Drawing Checker ハンドオフ

## 目的

特許図面画像から符号らしき英数字をOCR抽出し、将来的に明細書側の符号と照合する。

## MVP v0.1

実装対象：

```text
- jpg/png/gif画像読み込み
- 画像前処理
- OCR実行
- 英数字候補抽出
- bbox付きDrawingSign生成
- JSON出力
- 検出枠付き画像プレビューまたはHTML出力
- FastAPI API
```

## 技術スタック候補

```text
Python
FastAPI
Pydantic
OpenCV
Pillow
pytesseract または EasyOCR
pytest
```

初期はOCRエンジンを差し替え可能にする。

```python
class OcrEngine(Protocol):
    def recognize(self, image: ImageInput) -> list[OcrResult]:
        ...
```

## OCR結果モデル

```python
class OcrResult(BaseModel):
    text: str
    confidence: float | None = None
    bbox: BoundingBox
```

## DrawingSign抽出

OCR結果から、符号候補を抽出する。

初期ルール：

```text
- 数字のみ: 1, 10, 101
- 数字+英字: 10A, 20B
- 英字+数字: S1, L2
```

初期では、英字1文字だけは誤検出が多いため原則除外する。

除外例：

```text
- FIG
- ON
- OFF
- X
- Y
- %
```

設定例：

```yaml
drawing_sign:
  allow_numbers: true
  allow_letters_only: false
  allow_alphanumeric: true
  min_length: 1
  max_length: 6
  ignore_patterns:
    - "^FIG$"
    - "^ON$"
    - "^OFF$"
    - "^X$"
    - "^Y$"
```

## API

```text
GET  /health
POST /api/ocr-image
POST /api/check-image
POST /api/check-folder
POST /api/compare-signs
```

### `/api/ocr-image`

画像からOCR結果を返す。

### `/api/check-image`

画像からDrawingSignを抽出し、Diagnostics JSONを返す。

### `/api/compare-signs`

明細書側ReferenceSignリストと、図面側DrawingSignリストを照合する。

入力：

```json
{
  "spec_signs": [
    {
      "sign": "10",
      "label": "制御部",
      "source": "description",
      "locations": []
    }
  ],
  "drawing_signs": [
    {
      "sign": "10",
      "raw_text": "10",
      "normalized_sign": "10",
      "confidence": 0.91,
      "figure_id": "fig-1",
      "image_file": "fig1.png",
      "bbox": {
        "x": 100,
        "y": 120,
        "width": 30,
        "height": 20
      }
    }
  ]
}
```

出力：

```json
{
  "product": "drawing-checker",
  "diagnostics": [],
  "summary": {
    "error": 0,
    "warning": 0,
    "info": 0
  }
}
```

## Drawing Checker Rules

### DRAWING_SIGN_NOT_IN_SPEC

図面にある符号が明細書にない。

```text
図1に「12」があるが、明細書に符号12がない。
```

### SPEC_SIGN_NOT_IN_DRAWING

明細書にある符号が図面にない。

```text
明細書に「制御部10」があるが、図面に10がない。
```

初期では warning。

### POSSIBLE_OCR_MISREAD

OCR誤認識の可能性。

例：

```text
図面に「IO」がありますが、明細書に「10」があります。
```

誤認識候補：

```text
O ↔ 0
I ↔ 1
l ↔ 1
S ↔ 5
Z ↔ 2
B ↔ 8
```

### SIGN_LABEL_CONFLICT

同じ符号に複数名称が対応している。

これは主にDocument Checker側で検出するが、共通ルールとして扱えるようにする。

---

# Patent Drawing Checker UI方針

Document CheckerとはUIが異なるため、別UIにする。

## 必須UI

```text
- 画像ファイル選択
- 画像プレビュー
- OCR検出枠表示
- 検出符号一覧
- confidence表示
- JSON出力
```

## 将来UI

```text
- OCR結果の手動修正
- この検出を無視
- この符号は対象外
- OCR候補の修正履歴
- 明細書符号との一致/不一致表示
- HTMLレポート出力
```

---

# Document Checker と Drawing Checker の連携

将来、以下の連携を実装する。

```text
Document Checker
  ↓
明細書からReferenceSignを抽出
  ↓
reference_signs.json

Drawing Checker
  ↓
図面からDrawingSignを抽出
  ↓
drawing_signs.json

Sign Compare Engine
  ↓
Diagnostics JSON
```

統合入力：

```text
明細書.docx
drawings/
  fig1.png
  fig2.png
  fig3.png
```

統合出力：

```text
- document diagnostics
- drawing diagnostics
- sign compare diagnostics
- HTML report
```

---

# ローカルAPIサーバ構成

## Document Checker

```text
document-api
  /health
  /api/check-text
  /api/check-docx
  /api/check-ooxml
```

## Drawing Checker

```text
drawing-api
  /health
  /api/ocr-image
  /api/check-image
  /api/check-folder
  /api/compare-signs
```

将来的に統合APIを作る場合：

```text
suite-api
  /api/check-document
  /api/check-drawings
  /api/check-all
```

---

# Wordアドイン方針

WordアドインはDocument Checker側の入口として扱う。

```text
Word Add-in
  ↓
Local Document API
  ↓
Document Checker Core
```

Drawing CheckerはWordアドインに直接入れない。
図面チェックは別UIまたは外部アプリから実行する。

将来的にWord文書内に埋め込まれた画像を抽出する場合のみ、Word Add-inまたはdocx parser側で画像抽出を検討する。

---

# 配布方針

## 初期

```text
Patent Document Checker:
  - ローカルAPI
  - 簡易Web UI
  - 将来Wordアドイン
  - Wordアドインmanifestは共有フォルダ方式

Patent Drawing Checker:
  - ローカルAPI
  - 簡易Web UI
  - 画像ファイル/フォルダ入力
```

## 将来

```text
Patent Checker Suite:
  - Document Checker
  - Drawing Checker
  - Common Schema
  - 統合UI
  - 統合レポート
```

---

# Codexへの作業指示：改訂版

## まず作るもの

最初に **Patent Document Checker MVP v0.1** を実装する。

優先順位：

```text
1. Common Diagnostics schema
2. Document Core
3. 請求項抽出
4. 請求項番号チェック
5. 請求項引用関係チェック
6. マルチマルチチェック
7. FastAPI
8. HTMLレポート
```

この段階ではDrawing Checkerは実装しない。

ただし、以下の共通モデルは、Drawing Checkerでも使えるように設計しておく。

```text
- Diagnostic
- DiagnosticLocation
- BoundingBox
- ReferenceSign
- DrawingSign
```

## 次に作るもの

次に **Patent Drawing Checker MVP v0.1** を別プロダクトとして実装する。

優先順位：

```text
1. Common Diagnostics schemaを流用
2. 画像読み込み
3. OCR Engineインターフェース
4. OCR実行
5. 英数字候補抽出
6. DrawingSign JSON出力
7. 検出枠付きHTMLレポート
8. FastAPI
```

## 実装時の判断基準

迷った場合：

```text
- Document CheckerにOCR依存を入れない
- Drawing Checkerにdocx請求項解析を入れない
- 共通化するのはデータモデルとDiagnostics形式だけ
- UIは別々でよい
- APIも初期は別々でよい
- 将来統合できるようにJSONスキーマだけ揃える
```

---

# テスト方針

## Document Checker tests

```text
tests/document/
  test_claim_extraction.py
  test_claim_dependency.py
  test_rule_claim_numbering.py
  test_rule_multi_multi.py
  test_api_check_text.py
```

## Drawing Checker tests

```text
tests/drawing/
  test_drawing_sign_filter.py
  test_ocr_result_to_drawing_sign.py
  test_compare_signs.py
  test_possible_ocr_misread.py
```

## Common tests

```text
tests/common/
  test_diagnostic_schema.py
  test_reference_sign_schema.py
  test_drawing_sign_schema.py
```

---

# ログ方針

未公開特許情報を扱うため、ログには本文や画像内容を出さない。

ログに出してよいもの：

```text
- ファイル名
- 処理時間
- 請求項数
- 検出符号数
- エラー数
- 警告数
```

ログに出さないもの：

```text
- 明細書本文
- 請求項全文
- OOXML全文
- OCR全文
- 図面画像
```

---

# 最終的な方向性

このプロジェクトは、最終的に以下の形を目指す。

```text
Patent Checker Suite
  ├─ Document Checker
  │    └─ Word/docx特許書類チェック
  │
  ├─ Drawing Checker
  │    └─ 図面画像OCR・符号チェック
  │
  └─ Common
       └─ 符号・診断・レポート共通基盤
```

初期は別プロダクトとして軽く作る。
後から共通化しやすいように、Diagnostics JSONとReferenceSign/DrawingSignモデルだけを最初から揃える。
