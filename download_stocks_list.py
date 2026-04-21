import sys
import os
import logging
from datetime import date, timedelta
from pathlib import Path

import requests
import jpholiday

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
SAVE_DIR = Path(__file__).parent / "StocksList"


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and not jpholiday.is_holiday(d)


def nth_business_day(year: int, month: int, n: int) -> date:
    """Return the nth business day of the given year/month."""
    d = date(year, month, 1)
    count = 0
    while True:
        if is_business_day(d):
            count += 1
            if count == n:
                return d
        d += timedelta(days=1)


def should_run(today: date) -> bool:
    target = nth_business_day(today.year, today.month, 4)
    return today == target


def download(save_path: Path) -> None:
    logger.info(f"Downloading from {JPX_URL}")
    response = requests.get(JPX_URL, timeout=60)
    response.raise_for_status()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(response.content)
    logger.info(f"Saved to {save_path} ({len(response.content):,} bytes)")


if __name__ == "__main__":
    import pytz
    from datetime import datetime

    JST = pytz.timezone("Asia/Tokyo")
    today = datetime.now(JST).date()
    logger.info(f"Today (JST): {today}")

    if not should_run(today):
        target = nth_business_day(today.year, today.month, 4)
        logger.info(f"Not the 4th business day (target: {target}). Skipping.")
        sys.exit(0)

    logger.info("Today is the 4th business day of the month. Downloading.")
    filename = f"data_j_{today.strftime('%Y%m%d')}.xls"
    save_path = SAVE_DIR / filename
    download(save_path)
    logger.info("Done.")
