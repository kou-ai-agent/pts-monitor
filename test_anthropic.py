import os
try:
    from anthropic import Anthropic
except ImportError:
    print("Error: anthropic library is required. Please run `pip install anthropic`")
    import sys
    sys.exit(1)

def test_api():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ 環境変数 'ANTHROPIC_API_KEY' が設定されていません。")
        print("ターミナルで `export ANTHROPIC_API_KEY=\"あなたのAPIキー\"` を実行してから再度お試しください。")
        return

    print("APIキーを認識しました。Anthropic APIへの接続テスト（約1クレジット未満の消費）を開始します...")
    
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=50,
            messages=[{"role": "user", "content": "Hello! 課金チャージのテストです。うまく繋がっていたら一言返事をください。"}]
        )
        print("\n✅ テスト大成功！Claudeからの返答:")
        print("「" + response.content[0].text.strip() + "」")
        print("\nこれで課金トラブルは解消されています！本番環境（GitHub Actionsや main.py）でも問題なく稼働します！")
        
    except Exception as e:
        print(f"\n❌ テスト失敗。まだ課金が反映されていないか、APIキーが間違っている可能性があります。\nエラー内容: {e}")

if __name__ == "__main__":
    test_api()
