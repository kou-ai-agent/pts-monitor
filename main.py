import json
import logging
import os
from datetime import datetime, timezone, timedelta
from processor import generate_daily_json, DATA_DIR
from agent import generate_ai_content

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

    try:
        # 1. スクレイピングとデータ保存
        logger.info("Phase 1: Fetching and processing rankings...")
        generate_daily_json(today)

        # 2. AIによる要約・注目情報の生成
        logger.info("Phase 2: Generating AI Summaries and Highlights...")
        generate_ai_content(today)

        logger.info("--- Pipeline Finished Successfully ---")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
