# PTSモニター プロジェクト概要

## システム概要
PTS夜間取引データを株探からスクレイピングし、Claude APIで分析・Cloudflare Pagesで表示するモニタリングツール。

## 技術スタック
- データ取得：Python（scraper.py）
- AI分析：Claude API（claude-haiku-4-5）
- 実行環境：GitHub Actions（JST夜間スケジュール、月〜金UTC 15:30）
- フロントエンド：Cloudflare Pages（docs/）

## ファイル構成
- agent.py：Claude API分析（2-pass構成、TDNET/ニュース/IR並列取得）
- scraper.py：株探スクレイピング
- processor.py：データ整形・JSON保存
- main.py：エントリポイント
- notifier.py：LINE通知
- tdnet_scraper.py：TDNET適時開示取得
- news_scraper.py：ニュースRSS取得
- ir_scraper.py：企業IRページ取得
- download_stocks_list.py：JPX銘柄一覧月次DL
- docs/assets/app.js：フロントエンドJS（5ページ構成）
- docs/data/stocks_master.json：JPX銘柄マスタ

## 必須ルール
- タイムゾーンはJST（Asia/Tokyo）統一
- split_suspectedフラグで株式分割疑い銘柄を分析除外
- ETFフィルタ：stocks_master.jsonに存在しないコードをETFとみなす
- 複数ファイルにまたがる変更・新機能追加は実装前に変更計画をテキストで提示してから着手
- Actions実行時間は4〜5分以内を維持
