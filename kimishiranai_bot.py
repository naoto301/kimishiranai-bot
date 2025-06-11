from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# LINE Channel 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET       = os.getenv("CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)

# プレミアム判定用 GAS エンドポイント（後で貼る）
GAS_URL = "https://script.google.com/macros/s/AKfycbxBcVv1m-Q2mAznSBOo1oZYSCTTG-S3m6KET05yNY9Mg3jBNsGtxOE0UUdh-YbftrGW7g/exec"

# JSONファイルから全15話を読み込む
with open("kimishiranai_episodes_1to15.json", encoding="utf-8") as f:
    data = json.load(f)

# データを辞書化: key="1"〜"15"
story_data = {str(ep["episode"]): ep for ep in data.get("episodes", [])}

# 無料公開話数
FREE_LIMIT = 3
# アンロックコード
UNLOCK_CODE = "kimishiranai_unlock"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK", 200

# プレミアム判定関数
def is_premium_user(user_id: str) -> bool:
    try:
        resp = requests.get(GAS_URL, params={"user_id": user_id}, timeout=5)
        return resp.json().get("exists", False)
    except:
        return False

# プレミアム登録関数
def register_premium_user(user_id: str):
    try:
        requests.post(GAS_URL, json={"user_id": user_id}, timeout=5)
    except:
        pass

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text    = event.message.text.strip()
    user_id = event.source.user_id

    # Unlock コード
    if text == UNLOCK_CODE:
        register_premium_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ プレミアム解放完了！第4話以降が読めるようになりました。")
        )
        return

    # 数字入力チェック
    m = re.fullmatch(r"(\d{1,2})", text)
    if not m:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="『3』のように話数を数字で送ってください。")
        )
        return

    num = m.group(1)
    if num not in story_data:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="指定の話は存在しません。1〜15の数字を送ってください。")
        )
        return

    # 無料／有料振り分け
    idx = int(num)
    if idx > FREE_LIMIT and not is_premium_user(user_id):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔒 第4話以降はプレミアム限定です。"
        )
        return

    # 該当エピソードを送信
    ep = story_data[num]
    messages = []
    # サブタイトル if any
    title = ep.get("title") or ep.get("subtitle")
    if title:
        messages.append(TextSendMessage(text=title))
    # 吹き出し②〜⑤
    for line in ep.get("lines", []):
        messages.append(TextSendMessage(text=line.get("text")))

    line_bot_api.reply_message(event.reply_token, messages)

# 本番は gunicorn で起動
#if __name__ == "__main__":
#    port = int(os.environ.get("PORT", 10000))
#    app.run(host="0.0.0.0", port=port)
