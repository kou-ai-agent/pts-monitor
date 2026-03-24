import os
import json
import logging
from datetime import datetime
try:
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic library is required. Please run `pip install -r requirements.txt`")
    import sys
    sys.exit(1)

from processor import load_daily_json, save_daily_json

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
あなたは優秀な株式市場アナリストです。以下の本日のPTS（私設取引システム）ランキングデータを分析し、全体の特徴や傾向を3〜4文の自然な日本語で要約してください。
テーマ株への物色傾向、セクターの偏り、新興銘柄の動向、特異な動きがあれば言及してください。

【本日のPTSトップデータ】
- 値上がり率上位10: {[item['name'] + '(+' + str(item['change_pct']) + '%)' for item in price_up]}
- 値下がり率上位10: {[item['name'] + '(' + str(item['change_pct']) + '%)' for item in price_down]}
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

def _generate_highlights(client: Anthropic, rankings: dict) -> list:
    logger.info("Generating AI Highlights...")
    
    data_context = {
        "price_up": _extract_top_10(rankings, "price_up"),
        "price_down": _extract_top_10(rankings, "price_down"),
        "volume": _extract_top_10(rankings, "volume")
    }
    
    prompt = f"""
あなたは優秀な株式相場アナリストです。以下のPTSランキングデータ（値上がり・値下がり・出来高のトップ10）を分析し、**今日最も注目すべき銘柄を最大3〜5つ選定**してください。
選んだ理由（急騰の背景、出来高を伴う上昇など）を各2〜3文で解説してください。

【データ】
{json.dumps(data_context, ensure_ascii=False)}

以下のJSONフォーマットの「純粋な配列のみ」を出力してください。Markdown装飾(```json等)は絶対に含まないでください。

[
  {{
    "code": "1234",
    "name": "銘柄名",
    "reason": "選定理由。2〜3文で記載...",
    "rank_today": 1,
    "category": "price_up"
  }}
]
"""
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        result_text = response.content[0].text.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json\n", "").replace("\n```", "")
        elif result_text.startswith("```"):
            result_text = result_text.replace("```\n", "").replace("\n```", "")
            
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Highlights generation error ({type(e).__name__}): {e}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== AGENT TEST ({today}) ===")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("警告: 実行するには `export ANTHROPIC_API_KEY='your-key'` としてAPIキーを設定してください。")
    else:
        generate_ai_content(today)
        print("Done. Check data/ directory for AI contents.")
