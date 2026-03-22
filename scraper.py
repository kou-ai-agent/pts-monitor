import sys
import logging
from typing import List, Dict
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: requests and beautifulsoup4 are required. Please run `pip install -r requirements.txt`")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# カテゴリ名と株探URLパス
CATEGORY_MAP = {
    "price_up": "pts_night_price_increase",
    "price_down": "pts_night_price_decrease",
    "volume": "pts_night_volume_ranking",
    "turnover": "pts_night_trading_value_ranking"
}

# 市場と株探パラメータのマッピング
MARKET_MAP = {
    "all": "0",
    "prime": "1",
    "standard": "2",
    "growth": "3"
}

def _parse_float(val_str: str) -> float:
    try:
        val_str = val_str.replace(",", "").replace("%", "").replace("＋", "").replace("+", "")
        if val_str == "－" or val_str == "-":
            return 0.0
        return float(val_str)
    except:
        return 0.0

def _parse_int(val_str: str) -> int:
    try:
        val_str = val_str.replace(",", "").replace("千", "000").replace("万", "0000").replace("百万", "000000")
        if val_str == "－" or val_str == "-":
            return 0
        return int(float(val_str))
    except:
        return 0

def fetch_ranking(date: str, category: str, market: str) -> List[Dict]:
    """
    株探のPTSランキングページをスクレイピングし、データを取得する（100位まで対応）
    """
    path = CATEGORY_MAP.get(category, "pts_night_price_increase")
    market_val = MARKET_MAP.get(market, "0")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    results = []
    
    # 株探は1ページあたり15件。100位までのためには最大7ページ分を読み込む
    for page in range(1, 8):
        url = f"https://kabutan.jp/warning/{path}?market={market_val}&page={page}"
        
        try:
            logger.info(f"Fetching from: {url}")
            time.sleep(1.5) # 仕様書のサーバ負荷低減: 最低1.5秒空ける
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', class_='stock_table')
            
            if not table:
                logger.warning(f"Table not found on {url}")
                break

            rows = table.find_all('tr')
            # 値を含む行（tdが1つ以上ある行）のみ抽出
            data_rows = [tr for tr in rows if tr.find('td')]
            
            if not data_rows:
                # これ以上データがない（最終ページ到達）
                break

            for tr in data_rows:
                rank = len(results) + 1
                if rank > 100:  # 仕様通り100件まで
                    break
                    
                cells = tr.find_all(['th', 'td'])
                tds = [c.text.strip() for c in cells]
                if len(tds) < 10:
                    continue
                    
                code = tds[0]
                name = tds[1]
                try:
                    pts_price = _parse_float(tds[6])
                    change_pct = _parse_float(tds[8])
                    metric_val = _parse_int(tds[9])
                    
                    volume = 0
                    turnover = 0
                    if category == "turnover":
                        turnover = metric_val * 1000000 
                        if pts_price > 0:
                            volume = int(turnover / pts_price)
                    else:
                        volume = metric_val
                        turnover = int(volume * pts_price)
                    
                    results.append({
                        "rank": rank,
                        "code": code,
                        "name": name,
                        "price": pts_price,
                        "change_pct": change_pct,
                        "volume": volume,
                        "turnover": turnover
                    })
                except Exception as e:
                    logger.debug(f"Row parse error ({code} {name}): {e}")

            # 内部ループを抜けた後、100件に達していたら外側のループも抜ける
            if len(results) >= 100:
                break

        except Exception as e:
            logger.error(f"Failed to fetch data for {url}: {e}")
            break

    logger.info(f"Successfully fetched {len(results)} records for {category}-{market}.")
    return results

if __name__ == "__main__":
    print("=== Scraping Test: Price Increase (All Markets) ===")
    results = fetch_ranking("2026-03-20", "price_up", "all")
    print(f"Total fetched: {len(results)}")
    for r in results[:3]:  
        print(r)
    if len(results) > 3:
        print("...")
        print(results[-1]) # 最後の1件
