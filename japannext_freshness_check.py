"""
一時的な検証スクリプト。

Japannext証券の統計ページ2種類(値上がり率/値下がり率、相場ランキング)について、
Night Time / Day Timeセッションの見出しに表示されている日付を取得し、
japannext_freshness_log.csv に1行ずつ追記していく。

GitHub Actionsのスケジュール実行(.github/workflows/japannext_freshness_check.yml)
から呼び出す想定。本番パイプライン(main.py)には組み込まない。

検証が終わったら、対応するworkflowファイルとこのスクリプトごと削除してよい。
"""
import csv
import os
import re
import sys
from datetime import datetime, timezone, timedelta

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright is required. Run `pip install playwright && playwright install --with-deps chromium`")
    sys.exit(1)

JST = timezone(timedelta(hours=9))

PAGES_TO_CHECK = [
    ("market_movers", "値上がり率/値下がり率", "https://www.japannext.co.jp/ja/statistics/market-movers/turnover-and-market-share"),
    ("top_performers", "相場ランキング", "https://www.japannext.co.jp/ja/statistics/top-performers/turnover-and-market-share"),
]

LOG_PATH = "japannext_freshness_log.csv"

# 「【 2026年8月25日 】ナイトタイム・セッション」のようなテキストから日付とセッション種別を拾う
DATE_PATTERN = re.compile(r"【\s*(\d{4}年\d{1,2}月\d{1,2}日)\s*】\s*(ナイトタイム|デイタイム)")


def extract_dates(page_text):
    night = None
    day = None
    for date_str, session in DATE_PATTERN.findall(page_text):
        if session == "ナイトタイム" and night is None:
            night = date_str
        elif session == "デイタイム" and day is None:
            day = date_str
    return night, day


def main():
    now_utc = datetime.now(timezone.utc)
    now_jst = now_utc.astimezone(JST)

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
        )
        page = context.new_page()

        for key, label, url in PAGES_TO_CHECK:
            night_date = day_date = None
            status = None
            try:
                resp = page.goto(url, timeout=30000)
                status = resp.status if resp else None
                if status == 200:
                    text = page.inner_text("body")
                    night_date, day_date = extract_dates(text)
            except Exception as e:
                status = f"ERROR: {e}"

            row = {
                "checked_at_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "checked_at_jst": now_jst.strftime("%Y-%m-%d %H:%M:%S"),
                "page": key,
                "label": label,
                "http_status": status,
                "night_time_date": night_date,
                "day_time_date": day_date,
            }
            rows.append(row)
            print(row)

        browser.close()

    file_exists = os.path.exists(LOG_PATH)
    fieldnames = [
        "checked_at_utc", "checked_at_jst", "page", "label",
        "http_status", "night_time_date", "day_time_date",
    ]
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
