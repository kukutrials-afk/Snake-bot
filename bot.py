import os
import sqlite3
import threading
import time
import requests
from flask import Flask, request, jsonify

# Aapki sari details yahan pre-filled hain
BOT_TOKEN = "9244266282:AAHgdY5lTEoVudeisRtWL9mBrakQgXpuWF8"
BLOGGER_GAME_URL = "https://snakegameforplay.blogspot.com"

REWARD_VIDEOS = [
    "https://t.me/+QaORJhrhOTlkOTRl",
    "https://t.me/+tdcyzOAhvINkOTZl",
    "https://t.me/+V93BByxlJwJkZjM1"
]

def init_db():
    conn = sqlite3.connect("bot_users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    coins INTEGER DEFAULT 0,
                    unlocked_videos INTEGER DEFAULT 0,
                    referred_by INTEGER
                )''')
    conn.commit()
    conn.close()

init_db()

def send_msg(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

bot_username = ""
try:
    me = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10).json()
    if me.get("ok"):
        bot_username = me["result"]["username"]
except Exception:
    pass

def handle_update(upd):
    msg = upd.get("message")
    if not msg:
        return
    text = msg.get("text", "")
    user = msg.get("from", {})
    user_id = user.get("id")
    if not user_id:
        return

    if text.startswith("/start"):
        parts = text.split()
        referrer_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        conn = sqlite3.connect("bot_users.db")
        c = conn.cursor()
        c.execute("SELECT user_id, coins, unlocked_videos FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if not row:
            c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referrer_id))
            conn.commit()
            if referrer_id and referrer_id != user_id:
                c.execute("UPDATE users SET coins = coins + 25 WHERE user_id = ?", (referrer_id,))
                conn.commit()
                send_msg(referrer_id, "🎉 Aapke referral se ek dost ne bot join kiya! Aapko +25 bonus coins mile.")
            coins, unlocked = 0, 0
        else:
            coins, unlocked = row[1], row[2]
        conn.close()

        ref_link = f"https://t.me/{bot_username}?start={user_id}" if bot_username else f"User ID: {user_id}"
        play_url = f"{BLOGGER_GAME_URL}?uid={user_id}"

        keyboard = {
            "inline_keyboard": [
                [{"text": "🐍 Play Snake Game & Earn Coins", "url": play_url}],
                [{"text": "🎁 Share Referral Link (+25 Coins)", "url": f"https://t.me/share/url?url={ref_link}&text=Play%20Snake%20Game%20and%20unlock%20exclusive%20videos!"}]
            ]
        }

        reply_text = (
            f"👋 *Welcome to Snake Reward Bot!*\n\n"
            f"🪙 *Aapke Coins:* {coins}\n"
            f"🔓 *Unlocked Channels/Videos:* {unlocked}/3\n\n"
            f"🎯 *Rules:*\n"
            f"• Game khel kar *100 Coins / Length* banayein.\n"
            f"• 100 coins hote hi aapke *3 Exclusive Channels* unlock ho jayenge!\n\n"
            f"🔗 *Aapka Referral Link:*\n`{ref_link}`"
        )
        send_msg(user_id, reply_text, reply_markup=keyboard)

def poll_telegram():
    offset = 0
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 20},
                timeout=25
            )
            data = r.json()
            if data.get("ok"):
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    handle_update(upd)
        except Exception:
            time.sleep(2)

# Flask Web Server
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Snake Bot Server Running 24/7!"

@app.route("/api/add-coins", methods=["POST"])
def add_coins():
    data = request.json or {}
    user_id = data.get("user_id")
    earned_coins = data.get("coins", 0)

    if not user_id:
        return jsonify({"status": "error", "message": "User ID missing"}), 400

    conn = sqlite3.connect("bot_users.db")
    c = conn.cursor()
    c.execute("SELECT coins, unlocked_videos FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO users (user_id, coins) VALUES (?, ?)", (user_id, earned_coins))
        unlocked = 0
    else:
        unlocked = row[1]
        c.execute("UPDATE users SET coins = ? WHERE user_id = ?", (earned_coins, user_id))

    conn.commit()

    trigger_unlock = False
    if earned_coins >= 100 and unlocked == 0:
        c.execute("UPDATE users SET unlocked_videos = 3 WHERE user_id = ?", (user_id,))
        conn.commit()
        trigger_unlock = True

    conn.close()

    if trigger_unlock:
        send_msg(user_id, "🎉 *Badhaai ho!* Aapne game me 100 coins complete kar liye hain!\n\n🔓 *Yahan aapke 3 Unlocked Links hain:*")
        for i, vid in enumerate(REWARD_VIDEOS, 1):
            send_msg(user_id, f"🌟 *Unlocked Channel {i}:*\n{vid}")

    return jsonify({"status": "success", "unlocked": trigger_unlock})

if __name__ == "__main__":
    t = threading.Thread(target=poll_telegram, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
