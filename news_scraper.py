import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
RSS_FEEDS = [
    "https://www.nikkei.com/rss/news.rdf",
    "https://www.bloomberg.co.jp/feed/podcast/bloomberg-markets-japan.xml",
]


def _fetch_rss(url: str) -> list[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.warning(f"RSS {url} returned {r.status_code}")
            return []
        soup = BeautifulSoup(r.content, "xml")
        items = []
        for item in soup.find_all("item"):
            title_tag = item.find("title")
            link_tag = item.find("link")
            date_tag = item.find("pubDate") or item.find("date")
            desc_tag = item.find("description")
            items.append({
                "title": title_tag.get_text(strip=True) if title_tag else "",
                "link": link_tag.get_text(strip=True) if link_tag else "",
                "date": date_tag.get_text(strip=True) if date_tag else "",
                "description": desc_tag.get_text(strip=True) if desc_tag else "",
            })
        return items
    except Exception as e:
        logger.warning(f"RSS fetch failed {url}: {e}")
        return []


def _matches(article: dict, code: str, company_name: str) -> bool:
    text = f"{article['title']} {article['description']}"
    if code in text:
        return True
    if company_name and company_name in text:
        return True
    return False


def fetch_news(codes: list[str], company_names: dict[str, str]) -> dict:
    """
    codes: 銘柄コードリスト (例: ["3823", "6740"])
    company_names: コード→会社名 dict (例: {"3823": "日本テクノ"})
    戻り値: {code: {"status": "found"|"not_found"|"error", "articles": [...]}}
    """
    result = {code: {"status": "not_found", "articles": []} for code in codes}

    all_articles = []
    error_count = 0
    for url in RSS_FEEDS:
        articles = _fetch_rss(url)
        if not articles:
            error_count += 1
        all_articles.extend(articles)

    if error_count == len(RSS_FEEDS):
        for code in codes:
            result[code]["status"] = "error"
        return result

    for article in all_articles:
        for code in codes:
            if _matches(article, code, company_names.get(code, "")):
                entry = result[code]
                entry["status"] = "found"
                entry["articles"].append({
                    "title": article["title"],
                    "link": article["link"],
                    "date": article["date"],
                })

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    codes = ["3823", "6740"]
    company_names = {"3823": "日本テクノ", "6740": "ジャパンディスプレイ"}
    logger.info(f"Testing fetch_news for codes: {codes}")
    result = fetch_news(codes, company_names)

    print("\n=== 結果 ===")
    for code, data in result.items():
        print(f"\n[{code}] status={data['status']}  件数={len(data['articles'])}")
        for a in data["articles"][:3]:
            print(f"  {a['date']}  {a['title'][:60]}")
            print(f"    {a['link']}")
