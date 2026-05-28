import logging
from datetime import date, timedelta

import requests
import jpholiday
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.release.tdnet.info/inbs"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _business_days_before(target: date, n: int) -> list[date]:
    days = []
    d = target
    while len(days) < n:
        if d.weekday() < 5 and not jpholiday.is_holiday(d):
            days.append(d)
        d -= timedelta(days=1)
    return days


def _fetch_page(date_str: str, page: int) -> list[dict] | None:
    """1ページ分の開示情報を取得。ページが存在しない場合は None を返す。"""
    url = f"{BASE_URL}/I_list_{page:03d}_{date_str}.html"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find(id="main-list-table")
        if not table:
            return None
        rows = table.find_all("tr")
        if not rows:
            return None
        records = []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            records.append({
                "time":  tds[0].get_text(strip=True),
                "code":  tds[1].get_text(strip=True),
                "title_td": tds[3],
            })
        return records
    except requests.RequestException as e:
        logger.warning(f"Request failed {url}: {e}")
        return None


def _collect_day(date_obj: date) -> list[dict]:
    """1日分の全ページを収集して開示リストを返す。"""
    date_str = date_obj.strftime("%Y%m%d")
    date_label = date_obj.strftime("%Y-%m-%d")
    all_records = []
    page = 1
    while True:
        records = _fetch_page(date_str, page)
        if not records:
            break
        for rec in records:
            a = rec["title_td"].find("a")
            if not a:
                continue
            href = a.get("href", "")
            pdf_url = f"{BASE_URL}/{href}" if href else ""
            all_records.append({
                "date":    date_label,
                "time":    rec["time"],
                "code":    rec["code"],
                "title":   a.get_text(strip=True),
                "pdf_url": pdf_url,
            })
        page += 1
    return all_records


def fetch_tdnet(codes: list[str], business_days: int = 5) -> dict:
    import pytz
    from datetime import datetime

    JST = pytz.timezone("Asia/Tokyo")
    today = datetime.now(JST).date()
    target_dates = _business_days_before(today, business_days)

    result = {code: {"status": "not_found", "disclosures": []} for code in codes}

    # TDNETコードは4桁コード+取引所サフィックス1文字（例: 3823 → 38230）
    # startswith でマッチングする
    def _match_code(tdnet_code: str, stock_code: str) -> bool:
        return tdnet_code.startswith(stock_code) and len(tdnet_code) == len(stock_code) + 1

    try:
        for d in target_dates:
            logger.info(f"Fetching TDNET for {d}")
            day_records = _collect_day(d)
            for rec in day_records:
                matched = next((c for c in codes if _match_code(rec["code"], c)), None)
                if matched:
                    entry = result[matched]
                    entry["status"] = "found"
                    entry["disclosures"].append({
                        "date":    rec["date"],
                        "time":    rec["time"],
                        "title":   rec["title"],
                        "pdf_url": rec["pdf_url"],
                    })
    except Exception as e:
        logger.error(f"fetch_tdnet failed: {e}")
        for code in codes:
            if result[code]["status"] == "not_found":
                result[code]["status"] = "error"

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    codes = ["3823", "6740", "9999"]
    logger.info(f"Testing fetch_tdnet for codes: {codes}")
    result = fetch_tdnet(codes, business_days=5)

    print("\n=== 結果 ===")
    for code, data in result.items():
        print(f"\n[{code}] status={data['status']}  件数={len(data['disclosures'])}")
        for d in data["disclosures"]:
            print(f"  {d['date']} {d['time']}  {d['title'][:50]}")
            print(f"    {d['pdf_url']}")
