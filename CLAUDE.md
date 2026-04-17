# PTSモニター プロジェクト概要

## システム概要

PTS（私設取引システム）の夜間取引データを株探からスクレイピングし、Claude APIで分析・Cloudflare Pagesで表示するモニタリングツール。

## 技術スタック

- **データ取得**：Python（株探スクレイピング）
- **AI分析**：Claude API（claude-haiku-4-5）
- **実行環境**：GitHub Actions（毎日夜間スケジュール実行）
- **フロントエンド**：Cloudflare Pages（`docs/`以下の静的ファイル）

## ファイル構成

```
pts-monitor/
├── agent.py        # Claude APIによるAI分析（サマリ・注目銘柄ハイライト生成）
├── scraper.py      # 株探スクレイピング
├── processor.py    # データ整形・JSON保存・読み込み
├── main.py         # エントリポイント（スクレイピング→分析→保存の統括）
├── notifier.py     # LINE通知
├── docs/           # Cloudflare Pages用静的ファイル
└── .github/workflows/  # GitHub Actions定義
```

## 実装上の注意事項

- タイムゾーンは**JST（Asia/Tokyo）で統一**する
- 株式分割疑い銘柄は`split_suspected`フラグで管理し、分析から除外する
- GitHub Actionsのジョブ時間は通常4〜5分以内を維持すること

---

# MVP2 実装仕様（進行中）

## フェーズ1：agent.py改修（優先着手）

### 1-1. データコンテキストへの売買代金追加

`_generate_highlights()`内の`data_context`に`turnover`を追加する。

```python
# 変更前
data_context = {
    "price_up": _extract_top_10(rankings, "price_up"),
    "price_down": _extract_top_10(rankings, "price_down"),
    "volume": _extract_top_10(rankings, "volume")
}

# 変更後
data_context = {
    "price_up": _extract_top_10(rankings, "price_up"),
    "price_down": _extract_top_10(rankings, "price_down"),
    "volume": _extract_top_10(rankings, "volume"),
    "turnover": _extract_top_10(rankings, "turnover")  # 追加
}
```

### 1-2. プロンプトの選定指示を強化

`_generate_highlights()`のプロンプトに以下の指示を追加する。

```
選定した根拠として、以下を必ず含めてください。
- 選定に使用した具体的な数値（変化率・出来高・売買代金）
- 複数ランキングに登場している場合はその事実
- 推定・仮説の場合は「〜と推定」「〜の可能性」と明示すること
```

### 1-3. JSONフォーマットに`selection_basis`フィールドを追加

```json
{
  "code": "1234",
  "name": "銘柄名",
  "reason": "選定理由。推定は明示...",
  "selection_basis": {
    "change_pct": 10.79,
    "volume_rank": 3,
    "turnover_rank": 5,
    "appeared_in": ["price_up", "volume"]
  },
  "rank_today": 1,
  "category": "price_up"
}
```

---

## フェーズ2：UX改修

### 2-1. ページ構成（1ページ→5ページ）

| ページ | 名称 | 主なコンテンツ |
|--------|------|----------------|
| A | 全体サマリ＋注目セクター | 横断スコアリングによる注目セクター（3つ以上）、各セクターの注目銘柄（3つ以上）、ランキングなし |
| B | 出来高 | 市場選択プルダウン、注目銘柄（5つ）、ランキング、グラフ |
| C | 値上がり率 | 構成はBと同じ |
| D | 値下がり率 | 構成はBと同じ |
| E | 売買代金 | 構成はBと同じ |

### 2-2. ナビゲーション

- ドット5つ（A〜E）横並び
- 現在地ドット：白・やや大きめ
- その他ドット：グレー・小さめ
- 起点：ページA
- スマホ：フリックで左右移動
- PC：ページ端に半透明の左右ボタン

### 2-3. 注目セクター判定ロジック（ページA）

4指標の横断スコアリング（重み付き合計）で注目セクターを算出する。

| 指標 | 重み |
|------|------|
| 出来高 | 40% |
| 値上がり率 | 25% |
| 値下がり率 | 25% |
| 売買代金 | 10% |

### 2-4. 情報取得パイプライン（注目銘柄確定後）

```
株探スクレイピング
→ 注目銘柄リスト確定
→ 各銘柄に対してTDNET・ニュース・企業IRを並列取得
→ 取得結果（ステータス付き）をClaude APIのコンテキストに渡す
→ 分析文生成 → Cloudflare Pages表示
```

#### TDNET（適時開示）

- 取得方法：HTMLスクレイピング
- URL形式：`https://www.release.tdnet.info/inbs/I_list_001_YYYYMMDD.html`
- 取得期間：実行日を含む直近5営業日分
- 取得項目：開示日時・タイトル・PDFリンク
- PDFの中身読み込み：将来対応（MVP2対象外）

#### ニュース

- 取得元：日経RSS＋ブルームバーグRSSの2層
- 銘柄コード・会社名でフィルタリング

#### 企業IRページ

- 取得方法：株探の銘柄ページからIRリンクURLを取得（既存スクレイピングの延長）
- IRページトップの新着情報タイトルを取得

### 2-5. 情報取得ステータス定義

3ソース（TDNET・ニュース・企業IR）すべてに以下を適用する。

| ステータス | 意味 | UIへの表示 |
|------------|------|------------|
| 取得済み | 情報あり | 開示タイトル・リンクを表示 |
| 情報なし | 取得できたが該当情報がなかった | 「○○情報なし」と表示 |
| 取得不可 | URL特定失敗またはアクセスエラー | 「○○情報取得不可」と表示 |

**「情報なし」と「取得不可」はUIおよびClaude APIコンテキストの両方で明確に区別して渡すこと。**

---

## 将来対応（MVP2対象外）

- TDNETのPDF中身読み込み
- 企業IRページの深掘り取得
- 注目銘柄の選定件数拡張
