"""
一時的な診断スクリプト(第2弾)。
kabutan.jpがGitHub Actions経由のアクセスを405で拒否する問題(Playwright/requestsどちらでも
再現、IPベースのブロックと推定)を受けて、PTSの運営元であるジャパンネクスト証券の
公式統計ページ・CSVダウンロードがGitHub Actionsから利用できるかどうかを確認する。

本番パイプライン(main.py / scraper.py)には組み込まない。単発検証用。
検証が終わったらdaily.ymlの該当ステップと合わせて削除、または次の候補への差し替えでよい。
"""
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright is required. Run `pip install playwright && playwright install --with-deps chromium`")
    sys.exit(1)

PAGES_TO_CHECK = [
    ("値上がり率/値下がり率(ナイトタイム)", "https://www.japannext.co.jp/ja/statistics/market-movers/turnover-and-market-share"),
    ("売買代金ランキング(ナイトタイム)", "https://www.japannext.co.jp/ja/statistics/top-performers/turnover-and-market-share"),
]

CSV_TO_CHECK = [
    ("値上がり/値下がりCSV(ナイトタイム)", "https://www.japannext.co.jp/csv_download/dnd_market_movers/NGHT"),
    ("売買代金/出来高CSV(ナイトタイム)", "https://www.japannext.co.jp/csv_download/dnd_top_ranking/NGHT"),
]


def main():
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

        print("=== HTMLページの確認 (ブラウザナビゲーション) ===")
        for label, url in PAGES_TO_CHECK:
            try:
                resp = page.goto(url, timeout=30000)
                status = resp.status if resp else None
                print(f"[{label}] {url} -> status={status}")
                if status == 200:
                    table = page.query_selector("table")
                    if table:
                        rows = page.query_selector_all("table tr")
                        print(f"  table found: rows={len(rows)}")
                    else:
                        print("  table NOT found on page")
            except Exception as e:
                print(f"[{label}] Failed: {e}")

        print()
        print("=== CSVダウンロードの確認 (直接リクエスト) ===")
        for label, url in CSV_TO_CHECK:
            try:
                resp = context.request.get(url, timeout=30000)
                status = resp.status
                body = resp.body()
                print(f"[{label}] {url} -> status={status}, bytes={len(body)}")
                if status == 200:
                    try:
                        text = body.decode("utf-8")
                    except UnicodeDecodeError:
                        text = body.decode("shift_jis", errors="replace")
                    lines = text.splitlines()
                    print(f"  content-type={resp.headers.get('content-type')}")
                    print("  --- first 5 lines ---")
                    for line in lines[:5]:
                        print(f"  {line}")
            except Exception as e:
                print(f"[{label}] Failed: {e}")

        browser.close()


if __name__ == "__main__":
    main()
