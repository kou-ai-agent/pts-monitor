"""
Generates changelog entries from today's (JST) git commits using Claude API.
Prepends to docs/data/changelog.json if user-facing changes are detected.
Exits with code 0 on any error to avoid failing the workflow.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path

import pytz
import anthropic

CHANGELOG_PATH = Path(__file__).parent / "docs" / "data" / "changelog.json"
JST = pytz.timezone("Asia/Tokyo")

EXCLUDED_PATTERNS = [
    "automated daily pts data update",
    "automated monthly jpx stocks list download",
]


def get_todays_commits() -> tuple[list[str], str]:
    now_jst = datetime.now(JST)
    today_jst = now_jst.date()

    # Convert JST day boundaries to UTC for git log (Actions runs in UTC)
    since_jst = JST.localize(datetime.combine(today_jst, time(0, 0, 0)))
    until_jst = JST.localize(datetime.combine(today_jst, time(23, 59, 59)))
    since_utc = since_jst.astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
    until_utc = until_jst.astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")

    result = subprocess.run(
        ["git", "log", "--oneline", f"--after={since_utc}", f"--before={until_utc}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    filtered = [
        l for l in lines
        if not any(pat in l.lower() for pat in EXCLUDED_PATTERNS)
    ]
    return filtered, today_jst.strftime("%Y-%m-%d")


def get_next_version() -> str:
    if not CHANGELOG_PATH.exists():
        return "v1.0"
    with open(CHANGELOG_PATH, encoding="utf-8") as f:
        changelog = json.load(f)

    pattern = re.compile(r'^v(\d+)\.(\d+)$')
    versions = []
    for entry in changelog:
        m = pattern.match(entry.get("version", ""))
        if m:
            versions.append((int(m.group(1)), int(m.group(2))))

    if not versions:
        return "v1.0"

    major, minor = max(versions)
    return f"v{major}.{minor + 1}"


def generate_changelog_entry(commits: list[str], today_str: str) -> dict | None:
    client = anthropic.Anthropic()
    commits_text = "\n".join(commits)

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""以下のgitコミットログを分析し、ユーザー向けchangelogに記載すべき変更かどうかを判断してください。

コミットログ：
{commits_text}

判断基準：
- 記載すべき：UIの変更、新機能追加、ユーザーが体験できる機能改善、表示内容の変更
- 除外すべき：細かいバグ修正・リファクタリング・自動データ更新・テスト変更・ワークフロー設定変更

JSON形式のみで回答してください（説明文は不要）：
{{"should_include": true, "changes": ["ユーザー向けの簡潔な日本語での変更内容"]}}
または
{{"should_include": false, "changes": []}}""",
            }
        ],
    )

    response_text = message.content[0].text.strip()
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if not json_match:
        print(f"Could not parse Claude response: {response_text}")
        return None

    result = json.loads(json_match.group())
    if not result.get("should_include") or not result.get("changes"):
        return None

    return {
        "date": today_str,
        "version": get_next_version(),
        "changes": result["changes"],
    }


def prepend_to_changelog(entry: dict) -> None:
    changelog = []
    if CHANGELOG_PATH.exists():
        with open(CHANGELOG_PATH, encoding="utf-8") as f:
            changelog = json.load(f)

    changelog.insert(0, entry)

    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        json.dump(changelog, f, ensure_ascii=False, indent=2)
    print(f"Prepended {len(entry['changes'])} change(s) to {CHANGELOG_PATH}")


if __name__ == "__main__":
    try:
        commits, today_str = get_todays_commits()
    except Exception as e:
        print(f"Error getting commits: {e}")
        sys.exit(0)

    if not commits:
        print(f"No developer commits for {today_str} (JST). Skipping.")
        sys.exit(0)

    print(f"Found {len(commits)} developer commit(s) for {today_str}:")
    for c in commits:
        print(f"  {c}")

    try:
        entry = generate_changelog_entry(commits, today_str)
    except Exception as e:
        print(f"Error calling Claude API: {e}")
        sys.exit(0)

    if entry is None:
        print("No user-facing changes detected. Skipping changelog update.")
        sys.exit(0)

    try:
        prepend_to_changelog(entry)
    except Exception as e:
        print(f"Error updating changelog: {e}")
        sys.exit(0)
