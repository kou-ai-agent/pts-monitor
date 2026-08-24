"""
一時的な診断スクリプト。
kabutan.jpが2026-07-14頃からGitHub Actions経由のrequestsベースのリクエストを
405で拒否する問題について、Playwright(headless Chromium)経由なら通るかどうかを
確認するためだけのもの。

本番パイプライン(main.py / scraper.py)には組み込まない。
daily.ymlの検証用ステップから1回だけ実行し、結果を見たら
このファイルとdaily.ymlの該当ステップは削除してよい。
"""
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright is required. Run `pip install playwright && playwright install --with-deps chromium`")
    sys.exit(1)


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

        print("=== Step 1: kabutan.jp トップページ ===")
        try:
            resp = page.goto("https://kabutan.jp/", timeout=30000)
            print(f"status={resp.status if resp else 'N/A'}")
        except Exception as e:
            print(f"Failed to load top page: {e}")

        print("=== Step 2: PTSランキングページ (price_up / market=0 / page=1) ===")
        try:
            resp2 = page.goto(
                "https://kabutan.jp/warning/pts_night_price_increase?market=0&page=1",
                timeout=30000,
            )
            status2 = resp2.status if resp2 else None
            print(f"status={status2}")

            if status2 == 200:
                table = page.query_selector("table.stock_table")
                if table:
                    rows = page.query_selector_all("table.stock_table tr")
                    print(f"table found: rows={len(rows)}")
                else:
                    print("table NOT found (status 200 but no stock_table element - page structure may differ)")
            else:
                print("Ranking page did not return 200 - likely still blocked.")
        except Exception as e:
            print(f"Failed to load ranking page: {e}")

        browser.close()


if __name__ == "__main__":
    main()
