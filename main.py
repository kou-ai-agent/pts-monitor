import logging
from datetime import datetime, timezone, timedelta
from processor import generate_daily_json
from agent import generate_ai_content

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("main")
    
    JST = timezone(timedelta(hours=9))
    today = datetime.now(JST).strftime("%Y-%m-%d")
    logger.info(f"--- PTS Stock Check Pipeline Started for {today} ---")
    
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
