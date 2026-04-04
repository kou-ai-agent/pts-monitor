import os
import json
import logging
from datetime import datetime, timezone, timedelta
from scraper import fetch_ranking, CATEGORY_MAP, MARKET_MAP

logger = logging.getLogger(__name__)

# データ出力先ディレクトリ（Cloudflare Pagesで公開するため docs 配下に配置）
DATA_DIR = os.path.join(os.path.dirname(__file__), 'docs', 'data')

def generate_daily_json(target_date: str) -> str:
    """
    対象日付の全カテゴリ・市場のランキングを取得し、JSONとして保存する。
    Returns:
        保存されたJSONファイルのフルパス
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    rankings = {}
    for cat in CATEGORY_MAP.keys():
        rankings[cat] = {}
        for mkt in MARKET_MAP.keys():
            logger.info(f"Fetching {cat} - {mkt} for {target_date}")
            data = fetch_ranking(target_date, cat, mkt)
            rankings[cat][mkt] = data
            for item in rankings[cat][mkt]:
                if abs(item.get('change_pct', 0)) >= 40:
                    item['split_suspected'] = True
            
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST)
    generated_at = now.strftime("%H:%M:%S")
    
    # AI処理部分は後でagent.pyによって埋められるため、空または初期値にしておく
    daily_data = {
        "date": target_date,
        "generated_at": generated_at,
        "ai_summary": "",
        "ai_highlights": [],
        "rankings": rankings
    }
    
    file_path = os.path.join(DATA_DIR, f"{target_date}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(daily_data, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Saved {file_path}")
    
    _update_index()
    return file_path

def load_daily_json(target_date: str) -> dict:
    """
    指定された日付のJSONデータを読み込む（agent.py等で利用）
    """
    file_path = os.path.join(DATA_DIR, f"{target_date}.json")
    if not os.path.exists(file_path):
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_daily_json(target_date: str, data: dict) -> None:
    """
    指定された日付のJSONデータを上書き保存する（agent.py等で利用）
    """
    file_path = os.path.join(DATA_DIR, f"{target_date}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _update_index() -> None:
    """
    index.jsonを更新し、保持されているすべての日付をリストアップする
    """
    index_path = os.path.join(DATA_DIR, "index.json")
    dates = []
    
    if os.path.exists(DATA_DIR):
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".json") and filename != "index.json":
                date_str = filename.replace(".json", "")
                dates.append(date_str)
                
    dates.sort(reverse=True) # 最新の日付が先頭
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump({"dates": dates}, f, ensure_ascii=False, indent=2)
    logger.info(f"Updated index.json with {len(dates)} dates.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== PRROCESSOR TEST ({today}) ===")
    generate_daily_json(today)
    print("Done. Check data/ directory.")
