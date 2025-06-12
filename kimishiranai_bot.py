from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# LINE Bot credentials
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# GAS Web App URL（POSTを送信する先）
GAS_URL = "https://script.google.com/macros/s/AKfycbwoZzyGUYV1bT2cIJDIwAHj7srg7GjbM4ifZXS1Ds3z4p6koJIsv0AB4V7ApLDos7dOXg/exec"
UNLOCK_CODE = "kimishiranai_unlock"

# ストーリーデータの読み込み
with open("kimishiranai_episodes_1to15.json", "r", encoding="utf-8") as f:
    episodes = json.load(f)

# ヘルパー：プレミアムユーザーかどうかをGASに問い合わせ
def is_premium_user(user_id: str) -> bool:
    try:
        response = requests.get(GAS_URL, params={"user_id": user_id}, timeout=5)
        data = response.json()
        return data.get("exists", False)
    except Exception as e:
        print(f"[ERROR] Premium check failed: {e}")
        return False

# ヘルパー：プレミアムユーザーとしてGASに登録
def register_premium_user(user_id: str):
    try:
        print(f"[DEBUG] Registering premium user: {user_id}")
        response = requests.post(GAS_URL, json={"user_id": user_id}, timeout=5)
        print(f"[DEBUG] GAS response: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"[ERROR] Failed to register premium user: {e}")

# メインのWebhookエンドポイント
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# メッセージイベント処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # プレミアムアンロックコードの処理
    if text == UNLOCK_CODE:
        register_premium_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ プレミアム解放完了！第4話以降が読めるようになりました。")
        )
        return

    # 話数リクエスト処理（例：「3」など）
    if text.isdigit():
        episode_number = text
        if episode_number not in episodes:
            reply = "❌ 該当する話が見つかりませんでした。\n数字で話数を入力してください（例：1）"
        elif int(episode_number) >= 4 and not is_premium_user(user_id):
            reply = "🔒 この話を読むにはプレミアム登録が必要です。\nアンロックコードを入力してください。"
        else:
            reply = "\n\n".join(episodes[episode_number])
    else:
        reply = "📖 読みたい話数を数字で送ってください（例：1）"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

# サーバ起動用（RenderではPORT環境変数を使用）
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
