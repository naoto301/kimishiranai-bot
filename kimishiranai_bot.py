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

# Premium check endpoint
GAS_URL = os.getenv("GAS_URL")

# Load episodes
with open("kimishiranai_episodes_1to15.json", encoding="utf-8") as f:
    data = json.load(f)
story_data = {str(ep["episode"]): ep for ep in data.get("episodes", [])}

# プレミアム関連
tmp_FREE_LIMIT = 3
UNLOCK_CODE = "kimishiranai_unlock"

def is_premium_user(user_id: str) -> bool:
    try:
        resp = requests.get(GAS_URL, params={"user_id": user_id}, timeout=5)
        return resp.json().get("exists", False)
    except Exception:
        return False

def register_premium_user(user_id: str):
    try:
        requests.post(GAS_URL, json={"user_id": user_id}, timeout=5)
    except Exception:
        pass

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id

    if text == UNLOCK_CODE:
        register_premium_user(user_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ プレミアム解放完了！第4話以降が読めるようになりました。")
        )
        return

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
    if episode_index > tmp_FREE_LIMIT and not is_premium_user(user_id):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔒 第4話以降はプレミアム限定です。\nhttps://note.com/loyal_cosmos1726/n/ndee65edc41fb")
        )
        return

    ep = story_data[num]
    bubbles = [TextSendMessage(text=f"📕 第{ep['episode']}話「{ep['title']}」")]
    for line in ep["lines"]:
        bubbles.append(TextSendMessage(text=line["text"]))
    line_bot_api.reply_message(event.reply_token, bubbles)
