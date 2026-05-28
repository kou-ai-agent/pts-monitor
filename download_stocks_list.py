import sys
import json
import random
import logging
from datetime import date
from pathlib import Path

import requests
import xlrd

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
SAVE_DIR = Path(__file__).parent / "StocksList"
JSON_PATH = Path(__file__).parent / "docs" / "data" / "stocks_master.json"

MARKET_MAP = {
    "プライム（内国株式）": "東P",
    "スタンダード（内国株式）": "東S",
    "グロース（内国株式）": "東G",
}


def already_downloaded_this_month(today: date) -> bool:
    """今月分（yyyymm始まり）のファイルが StocksList/ に存在するか確認する。"""
    prefix = today.strftime("%Y%m")
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    return any(f.name.startswith(prefix) for f in SAVE_DIR.iterdir() if f.is_file())


def download(save_path: Path) -> bytes:
    logger.info(f"Downloading from {JPX_URL}")
    response = requests.get(JPX_URL, timeout=60)
    response.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(response.content)
    logger.info(f"Saved to {save_path} ({len(response.content):,} bytes)")
    return response.content


def convert_to_json(xls_bytes: bytes) -> dict:
    wb = xlrd.open_workbook(file_contents=xls_bytes)
    ws = wb.sheet_by_index(0)

    headers = [ws.cell_value(0, j) for j in range(ws.ncols)]
    idx = {h: i for i, h in enumerate(headers)}

    date_raw = ws.cell_value(1, idx["日付"])
    updated = str(int(date_raw))

    stocks = {}
    skipped = 0
    for row in range(1, ws.nrows):
        sector17 = ws.cell_value(row, idx["17業種区分"])
        if sector17 == "-":
            skipped += 1
            continue

        raw_code = ws.cell_value(row, idx["コード"])
        try:
            code = str(int(raw_code)) if isinstance(raw_code, float) else str(raw_code).strip()
        except (ValueError, TypeError):
            code = str(raw_code).strip()
        if not code or code == "0":
            skipped += 1
            continue
        name = ws.cell_value(row, idx["銘柄名"])
        market_raw = ws.cell_value(row, idx["市場・商品区分"])
        market = MARKET_MAP.get(market_raw, "")

        stocks[code] = {"name": name, "market": market, "sector17": sector17}

    logger.info(f"Converted: {len(stocks)} stocks (skipped {skipped} ETF/ETN rows)")
    return {"updated": updated, "stocks": stocks}


def save_json(data: dict) -> None:
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    logger.info(f"Saved JSON to {JSON_PATH}")


def verify(data: dict) -> None:
    stocks = data["stocks"]
    logger.info(f"=== 検証 ===")
    logger.info(f"総件数: {len(stocks)} 件  (updated: {data['updated']})")
    sample = random.sample(list(stocks.items()), min(5, len(stocks)))
    for code, info in sample:
        logger.info(f"  {code}: {info}")


if __name__ == "__main__":
    import pytz
    from datetime import datetime

    JST = pytz.timezone("Asia/Tokyo")
    today = datetime.now(JST).date()
    logger.info(f"Today (JST): {today}")

    if already_downloaded_this_month(today):
        logger.info(f"Today month {today.strftime('%Y%m')} already downloaded. Skipping.")
        sys.exit(0)

    logger.info("No download found for this month. Running.")
    filename = f"data_j_{today.strftime('%Y%m%d')}.xls"
    save_path = SAVE_DIR / filename

    xls_bytes = download(save_path)
    data = convert_to_json(xls_bytes)
    save_json(data)
    verify(data)
    logger.info("Done.")
