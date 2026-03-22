import os
import http.server
import socketserver
import webbrowser
import threading
import time

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

def start_server():
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving at port {PORT}")
            httpd.serve_forever()
    except OSError as e:
        print(f"エラー: ポート {PORT} が既に使用されているか、起動できません。 ({e})")
        print("別のターミナルでサーバーが起動したままになっていないか確認してください。")
        os._exit(1)

if __name__ == '__main__':
    # バックグラウンドでサーバーを起動
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 少し待ってからブラウザを自動展開
    time.sleep(1)
    url = f"http://localhost:{PORT}/docs/index.html"
    print(f"ブラウザで {url} を開きます...")
    webbrowser.open(url)
    
    print("\n※サーバーを終了するには [Ctrl + C] を押してください。")
    try:
        while True:
            time.sleep(100)
    except KeyboardInterrupt:
        print("\nサーバーを終了しました。")
