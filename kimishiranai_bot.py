from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import re
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# LINE Channel settings
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET       = os.getenv("CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)

# Premium check endpoint (update with your GAS URL)
GAS_URL = os.getenv("GAS_URL")  # e.g. "https://script.google.com/macros/s/..../exec"

# Load episodes (1-15) from JSON
with open("kimishiranai_episodes_1to15.json", encoding="utf-8") as f:
    data = json.load(f)
story_data = {str(ep["episode"]): ep for ep in data.get("episodes", [])}

# Unlock settings
tmp_FREE_LIMIT = 3
UNLOCK_CODE  = "kimishiranai_unlock"

# Helper: check if user is premium

def is_premium_user(user_id: str) -> bool:
    try:
        resp = requests.get(GAS_URL, params={"user_id": user_id}, timeout=5)
        return resp.json().get("exists", False)
    except Exception:
        return False

# Helper: register premium user

def register_premium_user(user_id: str):
    try:
        requests.post(GAS_URL, json={"user_id": user_id}, timeout=5)
    except Exception:
        pass

# Webhook callback
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# Message handler
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text    = event.message.text.strip()
    user_id = event.source.user_id

    # Unlock code logic
    if text == UNLOCK_CODE:
        register_premium_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ プレミアム解放完了！第4話以降が読めるようになりました。")
        )
        return

    # Expect numeric input
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

    episode_index = int(num)
    # Free vs premium check
    if episode_index > tmp_FREE_LIMIT and not is_premium_user(user_id):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔒 第4話以降はプレミアム限定です。\nhttps://note.com/loyal_cosmos1726/n/nefdff71e226f")
        )
        return

    # Send episode content
    ep = story_data[num]
    messages = []
    # Episode title
    if "title" in ep:
        messages.append(TextSendMessage(text=f"【第{num}話】 {ep['title']}"))
    # Lines ②〜⑤
    for line in ep.get("lines", []):
        messages.append(TextSendMessage(text=line.get("text", "")))

    line_bot_api.reply_message(event.reply_token, messages)

# Run with Gunicorn in production
# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 10000))
#     app.run(host="0.0.0.0", port=port)
