import logging
import re
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
KABUTAN_BASE = "https://kabutan.jp"


def _fetch_ir_url(code: str) -> str | None:
    """株探の銘柄ページからIRリンクURLを取得する。"""
    url = f"{KABUTAN_BASE}/stock/?code={code}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.warning(f"Kabutan {url} returned {r.status_code}")
            return None
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        # 除外ドメイン（株探ページに混在するサードパーティサイト）
        EXCLUDE = ["kabutan", "minkabu", "japannext", "hrmos", "twitter", "x.com",
                   "facebook", "youtube", "instagram", "linkedin"]

        company_url = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not href.startswith("http"):
                continue
            if any(ex in href for ex in EXCLUDE):
                continue
            # 株探は会社公式URLをリンクテキストとURLが同一の形式で表示する
            if text == href or text.rstrip("/") == href.rstrip("/"):
                company_url = href.rstrip("/")
                break

        if not company_url:
            return None

        # 会社サイトのIRページを探す（よくあるパスを順に試す）
        ir_paths = ["/ir/", "/investors/", "/investor/", "/ir_info/",
                    "/ir-info/", "/ir.html", "/investor_relations/"]
        for path in ir_paths:
            ir_url = company_url + path
            try:
                r2 = requests.get(ir_url, headers=HEADERS, timeout=10)
                if r2.status_code == 200:
                    return ir_url
            except Exception:
                continue

        # IRパスが見つからなければ会社トップを返す
        return company_url + "/"
    except Exception as e:
        logger.warning(f"Kabutan fetch failed for {code}: {e}")
        return None


def _fetch_ir_items(ir_url: str) -> list[dict]:
    """IRページのトップから新着情報タイトルを最大3件取得する。"""
    try:
        r = requests.get(ir_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            logger.warning(f"IR page {ir_url} returned {r.status_code}")
            return []
        r.encoding = r.apparent_encoding or "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        items = []

        # 「新着情報」「ニュース」「お知らせ」系のセクションを探す
        news_keywords = ["新着", "ニュース", "お知らせ", "news", "News", "NEWS", "topics", "Topics"]
        candidate_sections = []
        for kw in news_keywords:
            for tag in soup.find_all(["h2", "h3", "h4", "section", "div"], string=lambda s: s and kw in s):
                parent = tag.parent if tag.name in ["h2", "h3", "h4"] else tag
                candidate_sections.append(parent)

        for section in candidate_sections:
            for li in section.find_all("li")[:3]:
                a = li.find("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if not title:
                    continue
                if href and not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(ir_url, href)
                date_tag = li.find(class_=lambda c: c and any(d in c for d in ["date", "day", "time"]))
                items.append({
                    "title": title[:100],
                    "link": href,
                    "date": date_tag.get_text(strip=True) if date_tag else "",
                })
            if items:
                break

        # フォールバック1: h3/h4見出しからニュースタイトルを抽出（リンクなしの場合はIRページURLを使用）
        if not items:
            for tag in soup.find_all(["h3", "h4"]):
                title = tag.get_text(strip=True)
                if len(title) < 10:
                    continue
                a = tag.find("a") or (tag.parent.find("a") if tag.parent else None)
                href = a["href"] if a else ""
                if href and not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(ir_url, href)
                items.append({"title": title[:100], "link": href or ir_url, "date": ""})
                if len(items) >= 3:
                    break

        # フォールバック2: ページ全体のアンカーから長めのテキストを持つリンクを取得
        if not items:
            for a in soup.find_all("a", href=True)[:50]:
                title = a.get_text(strip=True)
                href = a["href"]
                if len(title) < 15:
                    continue
                if not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(ir_url, href)
                items.append({"title": title[:100], "link": href, "date": ""})
                if len(items) >= 3:
                    break

        return items[:3]
    except Exception as e:
        logger.warning(f"IR items fetch failed {ir_url}: {e}")
        return []


def fetch_ir(codes: list[str]) -> dict:
    """
    codes: 銘柄コードリスト (例: ["3823", "6740"])
    戻り値: {code: {"status": "found"|"not_found"|"error", "ir_url": str|None, "items": [...]}}
    """
    result = {code: {"status": "not_found", "ir_url": None, "items": []} for code in codes}

    for code in codes:
        try:
            ir_url = _fetch_ir_url(code)
            result[code]["ir_url"] = ir_url

            if ir_url is None:
                result[code]["status"] = "error"
                continue

            time.sleep(1)
            items = _fetch_ir_items(ir_url)
            if items:
                result[code]["status"] = "found"
                result[code]["items"] = items
            else:
                result[code]["status"] = "not_found"

        except Exception as e:
            logger.error(f"fetch_ir failed for {code}: {e}")
            result[code]["status"] = "error"

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    codes = ["3823", "6740"]
    logger.info(f"Testing fetch_ir for codes: {codes}")
    result = fetch_ir(codes)

    print("\n=== 結果 ===")
    for code, data in result.items():
        print(f"\n[{code}] status={data['status']}")
        print(f"  IR URL: {data['ir_url']}")
        for item in data["items"]:
            print(f"  {item['date']}  {item['title'][:60]}")
            print(f"    {item['link']}")
