import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
try:
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic library is required. Please run `pip install -r requirements.txt`")
    import sys
    sys.exit(1)

from processor import load_daily_json, save_daily_json
from tdnet_scraper import fetch_tdnet
from news_scraper import fetch_news
from ir_scraper import fetch_ir

logger = logging.getLogger(__name__)

# 使用するClaudeモデル（Haikuを指定）
MODEL_NAME = "claude-haiku-4-5"

def generate_ai_content(target_date: str) -> None:
    """
    保存された日次JSONデータを読み込み、Claude APIを用いてサマリーと注目銘柄ハイライトを生成、追記する。
    """
    # 環境変数から取得し、念のため前後に入り込んだ空白や改行を除去
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.error("環境変数 'ANTHROPIC_API_KEY' が設定されていません。AI処理をスキップします。")
        return
        
    client = Anthropic(api_key=api_key)
    
    data = load_daily_json(target_date)
    if not data or "rankings" not in data:
        logger.error(f"{target_date} のデータが見つからないか、不正なフォーマットです。")
        return
        
    rankings = data["rankings"]
    
    # 1. AIサマリー生成
    summary = _generate_summary(client, rankings)
    data["ai_summary"] = summary
    
    # 2. 注目銘柄ハイライト生成
    # ※ 本来は過去30日の履歴を全ロードしますが、稼働初期は過去データがないため当日データのみで分析します
    highlights = _generate_highlights(client, rankings)
    data["ai_highlights"] = highlights
    
    save_daily_json(target_date, data)
    logger.info(f"Successfully generated and saved AI contents for {target_date}")

def _extract_top_10(rankings: dict, category: str, market: str = "all") -> list:
    try:
        return rankings.get(category, {}).get(market, [])[:10]
    except:
        return []

def _generate_summary(client: Anthropic, rankings: dict) -> str:
    logger.info("Generating AI Summary...")
    
    price_up = _extract_top_10(rankings, "price_up")
    price_down = _extract_top_10(rankings, "price_down")
    volume = _extract_top_10(rankings, "volume")
    turnover = _extract_top_10(rankings, "turnover")
    
    prompt = f"""
あなたは優秀な株式市場アナリストです。以下の本日のPTS（私設取引システム）ランキングデータを分析し、3〜4文の自然な日本語で市場全体を解釈してください。

【分析の視点】
- 事実の列挙ではなく、**なぜその動きが起きたか**の仮説を前面に出してください
- 翌日の現物市場への示唆（どのセクターに資金が流入しやすいか等）を含めてください
- セクターローテーションの観点（資金がどこから来てどこへ向かっているか）で解釈してください
- [分割疑い]マークの付いた銘柄は株式分割の可能性があるため、値動き異常として扱わず分析から除外してください

【本日のPTSトップデータ】
- 値上がり率上位10: {[item['name'] + '(+' + str(item['change_pct']) + '%)' + ('[分割疑い]' if item.get('split_suspected') else '') for item in price_up]}
- 値下がり率上位10: {[item['name'] + '(' + str(item['change_pct']) + '%)' + ('[分割疑い]' if item.get('split_suspected') else '') for item in price_down]}
- 出来高上位10: {[item['name'] for item in volume]}
- 売買代金上位10: {[item['name'] for item in turnover]}

出力は要約文のテキストのみとしてください。
"""
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=300,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Summary generation error ({type(e).__name__}): {e}")
        return "AIサマリーの生成に失敗しました。"

def _fetch_external_info(codes: list, company_names: dict) -> dict:
    """TDNET・ニュース・IRを並列取得する。失敗しても他のソースは続行。"""
    results = {}

    def run(key, fn, *args):
        try:
            return key, fn(*args)
        except Exception as e:
            logger.error(f"{key} fetch failed: {e}")
            empty = {c: {"status": "error"} for c in codes}
            return key, empty

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(run, "tdnet", fetch_tdnet, codes),
            executor.submit(run, "news",  fetch_news,  codes, company_names),
            executor.submit(run, "ir",    fetch_ir,    codes),
        ]
        for f in as_completed(futures):
            key, data = f.result()
            results[key] = data

    return results


def _format_external_context(highlights: list, external: dict) -> str:
    """外部情報をプロンプト用テキストに整形する。"""
    lines = ["【外部情報】"]
    for h in highlights:
        code, name = h["code"], h["name"]
        lines.append(f"\n■ {code} {name}")

        tdnet = external.get("tdnet", {}).get(code, {"status": "error", "disclosures": []})
        lines.append(f"  TDNET: {tdnet['status']}")
        for d in tdnet.get("disclosures", [])[:3]:
            lines.append(f"    - {d['date']} {d['time']} 「{d['title']}」(PDF: {d['pdf_url']})")

        news = external.get("news", {}).get(code, {"status": "error", "articles": []})
        lines.append(f"  ニュース: {news['status']}")
        for a in news.get("articles", [])[:3]:
            lines.append(f"    - 「{a['title']}」({a['link']})")

        ir = external.get("ir", {}).get(code, {"status": "error", "items": []})
        lines.append(f"  IR: {ir['status']}")
        for item in ir.get("items", [])[:3]:
            lines.append(f"    - 「{item['title']}」({item['link']})")

    lines += [
        "\n【ステータス定義】",
        "- found：情報あり",
        "- not_found：取得できたが該当情報なし",
        "- error：取得不可",
    ]
    return "\n".join(lines)


def _generate_highlights(client: Anthropic, rankings: dict) -> list:
    logger.info("Generating AI Highlights...")
    
    data_context = {
        "price_up": _extract_top_10(rankings, "price_up"),
        "price_down": _extract_top_10(rankings, "price_down"),
        "volume": _extract_top_10(rankings, "volume"),
        "turnover": _extract_top_10(rankings, "turnover")
    }
    
    prompt = f"""
あなたは優秀な株式相場アナリストです。以下のPTSランキングデータ（値上がり・値下がり・出来高・売買代金のトップ10）を分析し、**今日最も注目すべき銘柄を最大3〜5つ選定**してください。

【split_suspected=trueの銘柄について】
split_suspected=trueの銘柄は株式分割の可能性があるため、急騰・急落の値動き異常として扱わず、選定対象から外してください。

【除外対象銘柄について】
以下の銘柄は注目銘柄の選定対象から除外してください：
- ETF・投資信託・指数連動商品（証券コードが1000〜1999番台、例：日経レバ1570、日経ベア2 1360、日経ブル2 1579）
- コモディティETF（WTI原油1671、純金信託1540、純銀信託1542など）
- インバース・レバレッジ型商品全般

【選定理由（reasonフィールド）の必須要素】
以下の3点を必ず含む2〜3文で記述してください：
1. 数値的根拠（変化率・出来高・売買代金など具体的な数値）
2. 動いた仮説（なぜその動きが起きたかの仮説・背景）
3. 翌日注目点（翌日の現物市場でどこに注目すべきか）

【選定根拠（selection_basisフィールド）の必須要素】
以下を必ず含めてください：
- 選定に使用した具体的な数値（change_pct・volume_rank・turnover_rank）
- 複数ランキングに登場している場合はappeared_inにそのランキング名をすべて列挙
- 推定・仮説の場合は reasonフィールドで「〜と推定」「〜の可能性」と明示すること

【注意】「材料を確認してください」という表現は、急騰・急落の背景が全く不明な場合に限り使用してください。それ以外では具体的な仮説を記述してください。

【データ】
{json.dumps(data_context, ensure_ascii=False)}

以下のJSONフォーマットの「純粋な配列のみ」を出力してください。Markdown装飾(```json等)は絶対に含まないでください。

[
  {{
    "code": "1234",
    "name": "銘柄名",
    "reason": "選定理由。数値的根拠・動いた仮説・翌日注目点の3点を含む2〜3文で記載...",
    "selection_basis": {{
      "change_pct": 10.79,
      "volume_rank": 3,
      "turnover_rank": 5,
      "appeared_in": ["price_up", "volume"]
    }},
    "rank_today": 1,
    "category": "price_up"
  }}
]
"""
    def _parse_json_response(text: str) -> list:
        text = text.strip()
        if text.startswith("```json"):
            text = text.replace("```json\n", "").replace("\n```", "")
        elif text.startswith("```"):
            text = text.replace("```\n", "").replace("\n```", "")
        return json.loads(text)

    # Pass 1: 注目銘柄選定
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1500,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        highlights = _parse_json_response(response.content[0].text)
    except Exception as e:
        logger.error(f"Highlights pass1 error ({type(e).__name__}): {e}")
        return []

    if not highlights:
        return []

    # Pass 2: 外部情報取得 → reason強化
    codes = [h["code"] for h in highlights]
    company_names = {h["code"]: h["name"] for h in highlights}

    logger.info(f"Fetching external info for {codes} ...")
    external = _fetch_external_info(codes, company_names)

    # external_info_status を各highlightに付与、UIリンク用URLも保存
    for h in highlights:
        code = h["code"]
        tdnet_data = external.get("tdnet", {}).get(code, {})
        news_data  = external.get("news",  {}).get(code, {})
        ir_data    = external.get("ir",    {}).get(code, {})

        h["external_info_status"] = {
            "tdnet": tdnet_data.get("status", "error"),
            "news":  news_data.get("status", "error"),
            "ir":    ir_data.get("status", "error"),
        }
        disclosures = tdnet_data.get("disclosures", [])
        if disclosures:
            h["tdnet_url"] = disclosures[0].get("pdf_url", "")
        articles = news_data.get("articles", [])
        if articles:
            h["news_url"] = articles[0].get("link", "")
        ir_url = ir_data.get("ir_url")
        if ir_url:
            h["ir_url"] = ir_url

    ext_context = _format_external_context(highlights, external)

    prompt_pass2 = f"""
あなたは優秀な株式相場アナリストです。
以下の「注目銘柄リスト（Pass1）」に、「外部情報」を加味してreasonフィールドのみを更新してください。

【注目銘柄リスト（Pass1）】
{json.dumps(highlights, ensure_ascii=False)}

{ext_context}

【更新ルール】
- 外部情報（TDNET・ニュース・IR）にfoundな情報があればreasonに組み込んでください
- 情報がnot_foundまたはerrorの場合はPass1のreasonをそのまま維持してください
- code・name・selection_basis・rank_today・category・external_info_statusは変更しないでください
- 推定・仮説は「〜と推定」「〜の可能性」と明示してください

以下のJSONフォーマットの「純粋な配列のみ」を出力してください。Markdown装飾(```json等)は絶対に含まないでください。
"""
    try:
        response2 = client.messages.create(
            model=MODEL_NAME,
            max_tokens=2000,
            temperature=0.5,
            messages=[{"role": "user", "content": prompt_pass2}]
        )
        enriched = _parse_json_response(response2.content[0].text)
        # external_info_statusをPass1の値で上書き保証
        status_map = {h["code"]: h["external_info_status"] for h in highlights}
        for h in enriched:
            if h["code"] in status_map:
                h["external_info_status"] = status_map[h["code"]]
        return enriched
    except Exception as e:
        logger.error(f"Highlights pass2 error ({type(e).__name__}): {e}")
        return highlights  # Pass1結果にフォールバック

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== AGENT TEST ({today}) ===")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("警告: 実行するには `export ANTHROPIC_API_KEY='your-key'` としてAPIキーを設定してください。")
    else:
        generate_ai_content(today)
        print("Done. Check data/ directory for AI contents.")
