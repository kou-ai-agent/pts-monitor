import os
import logging
import requests

logger = logging.getLogger(__name__)

# GitHub Secretsから取得する環境変数名（PTSモニター専用チャンネル）
PTS_DISCORD_WEBHOOK_URL = os.environ.get("PTS_DISCORD_WEBHOOK_URL", "")
PTS_SLACK_WEBHOOK_URL   = os.environ.get("PTS_SLACK_WEBHOOK_URL", "")
PTS_LINE_ACCESS_TOKEN   = os.environ.get("PTS_LINE_ACCESS_TOKEN", "")

def send_notification(report: dict) -> None:
    """
    バッチ実行レポートをDiscord・Slack・LINEに送信する。
    report = {
        "date": str,
        "ai_summary_ok": bool,
        "ai_highlights_count": int,
        "fetch_counts": { "category-market": int, ... },
        "fail_counts": { "category-market": int, ... },
        "total_fails": int,
    }
    """
    message = _build_message(report)
    _send_discord(message)
    _send_slack(message)
    _send_line(message)

def _build_message(report: dict) -> str:
    date         = report.get("date", "unknown")
    summary_ok   = "✅ 生成OK" if report.get("ai_summary_ok") else "❌ 失敗"
    hl_count     = report.get("ai_highlights_count", 0)
    highlights   = f"✅ {hl_count}件" if hl_count > 0 else "❌ 0件（未生成）"
    total_fails  = report.get("total_fails", 0)
    fetch_counts = report.get("fetch_counts", {})
    fail_counts  = report.get("fail_counts", {})

    lines = [
        f"📊 **PTS Monitor 日次レポート [{date}]**",
        "",
        f"✨ AIサマリー : {summary_ok}",
        f"🔥 注目銘柄   : {highlights}",
        "",
        "📈 情報取得件数（カテゴリ別・市場別）",
    ]

    # カテゴリ表示名
    CAT_LABEL = {
        "price_up": "値上がり率",
        "price_down": "値下がり率",
        "volume": "出来高",
        "turnover": "売買代金"
    }
    MKT_LABEL = {
        "all": "全市場",
        "prime": "プライム",
        "standard": "スタンダード",
        "growth": "グロース"
    }

    for cat in ["price_up", "price_down", "volume", "turnover"]:
        cat_label = CAT_LABEL.get(cat, cat)
        row_parts = []
        for mkt in ["all", "prime", "standard", "growth"]:
            key = f"{cat}-{mkt}"
            cnt = fetch_counts.get(key, 0)
            fail = fail_counts.get(key, 0)
            mkt_label = MKT_LABEL.get(mkt, mkt)
            status = f"{cnt}件" + (f"(失敗{fail}件)" if fail > 0 else "")
            row_parts.append(f"{mkt_label}:{status}")
        lines.append(f"  {cat_label}: " + " / ".join(row_parts))

    lines += [
        "",
        f"⚠️ 合計失敗件数: {total_fails}件" if total_fails > 0 else "✅ 全件取得成功",
    ]

    return "\n".join(lines)

def _send_discord(message: str) -> None:
    if not PTS_DISCORD_WEBHOOK_URL:
        logger.warning("PTS_DISCORD_WEBHOOK_URL が設定されていません。")
        return
    try:
        resp = requests.post(PTS_DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        resp.raise_for_status()
        logger.info("Discord通知を送信しました。")
    except Exception as e:
        logger.error(f"Discord通知エラー: {e}")

def _send_slack(message: str) -> None:
    if not PTS_SLACK_WEBHOOK_URL:
        logger.warning("PTS_SLACK_WEBHOOK_URL が設定されていません。")
        return
    # Slackはmarkdownのbold記法が異なるため ** を * に置換
    slack_text = message.replace("**", "*")
    try:
        resp = requests.post(PTS_SLACK_WEBHOOK_URL, json={"text": slack_text}, timeout=10)
        resp.raise_for_status()
        logger.info("Slack通知を送信しました。")
    except Exception as e:
        logger.error(f"Slack通知エラー: {e}")

def _send_line(message: str) -> None:
    if not PTS_LINE_ACCESS_TOKEN:
        logger.warning("PTS_LINE_ACCESS_TOKEN が設定されていません。")
        return
    # LINEはmarkdown非対応のため記号を除去
    line_text = message.replace("**", "").replace("✅", "OK").replace("❌", "NG")
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {
        "Authorization": f"Bearer {PTS_LINE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(url, headers=headers, json={"messages": [{"type": "text", "text": line_text}]}, timeout=10)
        resp.raise_for_status()
        logger.info("LINE通知を送信しました。")
    except Exception as e:
        logger.error(f"LINE通知エラー: {e}")
