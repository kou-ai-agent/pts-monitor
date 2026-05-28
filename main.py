import json
import logging
import os
from datetime import datetime, timezone, timedelta
from processor import generate_daily_json, DATA_DIR
from agent import generate_ai_content
from notifier import send_notification

def _has_valid_data(target_date: str) -> bool:
    """当日分JSONが存在し、rankingsが空でない場合 True を返す"""
    file_path = os.path.join(DATA_DIR, f"{target_date}.json")
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        rankings = data.get("rankings", {})
        # 全カテゴリ×市場のいずれかに1件以上データがあれば有効とみなす
        return any(
            len(rows) > 0
            for cat in rankings.values()
            for rows in cat.values()
        )
    except Exception:
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("main")

    JST = timezone(timedelta(hours=9))
    today = datetime.now(JST).strftime("%Y-%m-%d")
    logger.info(f"--- PTS Stock Check Pipeline Started for {today} ---")

    if _has_valid_data(today):
        logger.info(f"Data for {today} already exists with valid rankings. Skipping pipeline.")
        exit(0)

    # 通知レポート用の集計変数
    fetch_counts = {}
    fail_counts  = {}
    total_fails  = 0

    try:
        # Phase 1: スクレイピング＆データ保存
        logger.info("Phase 1: Fetching and processing rankings...")

        # generate_daily_json 内部のスクレイピング結果を取得するために
        # scraper を直接呼び出して件数を計測する
        from scraper import fetch_ranking, CATEGORY_MAP, MARKET_MAP
        from processor import load_daily_json, _update_index

        os.makedirs(DATA_DIR, exist_ok=True)

        rankings = {}
        for cat in CATEGORY_MAP.keys():
            rankings[cat] = {}
            for mkt in MARKET_MAP.keys():
                logger.info(f"Fetching {cat} - {mkt} for {today}")
                data = fetch_ranking(today, cat, mkt)
                rankings[cat][mkt] = data
                key = f"{cat}-{mkt}"
                fetch_counts[key] = len(data)
                fail_counts[key] = 0
                if len(data) == 0:
                    fail_counts[key] = 1
                    total_fails += 1

        now_str = datetime.now(JST).strftime("%H:%M:%S")
        daily_data = {
            "date": today,
            "generated_at": now_str,
            "ai_summary": "",
            "ai_highlights": [],
            "rankings": rankings
        }

        file_path = os.path.join(DATA_DIR, f"{today}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {file_path}")
        _update_index()

        # Phase 2: AI コンテンツ生成
        logger.info("Phase 2: Generating AI Summaries and Highlights...")
        generate_ai_content(today)

        # AI生成結果を読み込んで通知レポートに反映
        result_data = load_daily_json(today)
        ai_summary_ok = bool(result_data.get("ai_summary") and result_data["ai_summary"] != "AIサマリーの生成に失敗しました。")
        ai_highlights_count = len(result_data.get("ai_highlights", []))

        logger.info("--- Pipeline Finished Successfully ---")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        ai_summary_ok = False
        ai_highlights_count = 0

    # Phase 3: 通知送信
    logger.info("Phase 3: Sending notifications...")
    report = {
        "date": today,
        "ai_summary_ok": ai_summary_ok,
        "ai_highlights_count": ai_highlights_count,
        "fetch_counts": fetch_counts,
        "fail_counts": fail_counts,
        "total_fails": total_fails,
    }
    send_notification(report)
    logger.info("--- All Done ---")
