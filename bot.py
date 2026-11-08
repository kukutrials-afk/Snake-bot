import os
import sqlite3
import threading
import time
import requests
from flask import Flask, request, jsonify

BOT_TOKEN = "9244266282:AAHgdY5lTEoVudeisRtWL9mBrakQgXpuWF8"
BLOGGER_GAME_URL = "https://snakegameforplay.blogspot.com"
COIN_COST_PER_VIDEO = 10

def init_db():
    conn = sqlite3.connect("bot_users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    coins INTEGER DEFAULT 0,
                    videos_watched INTEGER DEFAULT 0,
                    referred_by INTEGER
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER,
                    message_id INTEGER,
                    UNIQUE(channel_id, message_id)
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
        return requests.post(url, json=payload, timeout=10).json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def copy_message(to_chat_id, from_chat_id, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage"
    payload = {
        "chat_id": to_chat_id,
        "from_chat_id": from_chat_id,
        "message_id": message_id
    }
    try:
        res = requests.post(url, json=payload, timeout=15).json()
        return res.get("ok", False)
    except Exception as e:
        print(f"Error copying video: {e}")
        return False

bot_username = ""
try:
    me = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=10).json()
    if me.get("ok"):
        bot_username = me["result"]["username"]
except Exception:
    pass

def get_main_menu(user_id, coins, watched):
    ref_link = f"https://t.me/{bot_username}?start={user_id}" if bot_username else f"ID: {user_id}"
    play_url = f"{BLOGGER_GAME_URL}?uid={user_id}"

    keyboard = {
        "inline_keyboard": [
            [{"text": f"🎬 Unlock Video (-{COIN_COST_PER_VIDEO} Coins)", "callback_data": "unlock_video"}],
            [{"text": "🐍 Play Snake Game (Earn Coins)", "url": play_url}],
            [{"text": "🎁 Share Referral Link (+25 Coins)", "url": f"https://t.me/share/url?url={ref_link}&text=Play%20Snake%20Game%20and%20unlock%20exclusive%20videos!"}]
        ]
    }

    text = (
        f"👋 *Welcome to Snake Reward Bot!*\n\n"
        f"🪙 *Aapke Wallet Coins:* {coins}\n"
        f"🎬 *Videos Watched:* {watched}\n"
        f"💎 *Rate:* {COIN_COST_PER_VIDEO} Coins = 1 Video\n\n"
        f"🎯 *Kaise use karein:*\n"
        f"• *'🎬 Unlock Video'* dabakar channel se direct video dekhein.\n"
        f"• *'🐍 Play Snake Game'* khel kar har match me coins kamayein!\n\n"
        f"🔗 *Aapka Referral Link:*\n`{ref_link}`"
    )
    return text, keyboard

def handle_update(upd):
    # Channel me video aane par auto-detect
    if "channel_post" in upd:
        post = upd["channel_post"]
        ch_id = post["chat"]["id"]
        msg_id = post["message_id"]
        conn = sqlite3.connect("bot_users.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO videos (channel_id, message_id) VALUES (?, ?)", (ch_id, msg_id))
        conn.commit()
        conn.close()
        return

    # Button click
    if "callback_query" in upd:
        call = upd["callback_query"]
        user_id = call["from"]["id"]
        data = call.get("data")
        call_id = call.get("id")

        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": call_id}, timeout=5)
        except Exception:
            pass

        if data == "unlock_video":
            conn = sqlite3.connect("bot_users.db")
            c = conn.cursor()
            c.execute("SELECT coins, videos_watched FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
            coins = row[0] if row else 0
            watched = row[1] if row else 0

            if coins < COIN_COST_PER_VIDEO:
                conn.close()
                play_url = f"{BLOGGER_GAME_URL}?uid={user_id}"
                alert_kb = {
                    "inline_keyboard": [
                        [{"text": "🐍 Play Game to Earn Coins", "url": play_url}]
                    ]
                }
                send_msg(user_id, f"⚠️ *Coins kam hain!*\n\n1 Video unlock karne ke liye *{COIN_COST_PER_VIDEO} Coins* chahiye.\nAapke paas sirf *{coins} Coins* hain.\n\nSnake Game khel kar aur coins kamayein!", reply_markup=alert_kb)
                return

            c.execute("SELECT COUNT(*) FROM videos")
            total_vids = c.fetchone()[0]

            if total_vids == 0:
                conn.close()
                send_msg(user_id, "⚠️ Channel me abhi aur videos add ho rahe hain, thodi der me koshish karein!")
                return

            offset = watched % total_vids
            c.execute("SELECT channel_id, message_id FROM videos ORDER BY id ASC LIMIT 1 OFFSET ?", (offset,))
            v_row = c.fetchone()

            if v_row:
                ch_id, msg_id = v_row[0], v_row[1]
                success = copy_message(user_id, ch_id, msg_id)
                if success:
                    new_coins = coins - COIN_COST_PER_VIDEO
                    new_watched = watched + 1
                    c.execute("UPDATE users SET coins = ?, videos_watched = ? WHERE user_id = ?", (new_coins, new_watched, user_id))
                    conn.commit()
                    text, kb = get_main_menu(user_id, new_coins, new_watched)
                    send_msg(user_id, f"🎉 *Video Unlocked!*\n-{COIN_COST_PER_VIDEO} Coins kate. Bacha hua balance: *{new_coins} Coins*.\n\nAgla video dekhne ke liye dubara button dabayein 👇", reply_markup=kb)
                else:
                    send_msg(user_id, "⚠️ Video send nahi ho payi. Check karein ki bot channel me Admin hai ya nahi.")
            conn.close()
        return

    # User messages (/start)
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
        c.execute("SELECT user_id, coins, videos_watched FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()

        if not row:
            c.execute("INSERT INTO users (user_id, referred_by) VALUES (?, ?)", (user_id, referrer_id))
            conn.commit()
            if referrer_id and referrer_id != user_id:
                c.execute("UPDATE users SET coins = coins + 25 WHERE user_id = ?", (referrer_id,))
                conn.commit()
                send_msg(referrer_id, "🎉 Aapke referral se ek dost ne bot join kiya! Aapko +25 bonus coins mile.")
            coins, watched = 0, 0
        else:
            coins, watched = row[1], row[2]
        conn.close()

        menu_text, menu_kb = get_main_menu(user_id, coins, watched)
        send_msg(user_id, menu_text, reply_markup=menu_kb)

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

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Snake Reward Bot Running 24/7!"

# Yahan har game ke coins user wallet me add hote hain
@app.route("/api/add-coins", methods=["POST"])
def add_coins():
    data = request.json or {}
    user_id = data.get("user_id")
    earned_coins = data.get("coins", 0)

    if not user_id or earned_coins <= 0:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    conn = sqlite3.connect("bot_users.db")
    c = conn.cursor()
    c.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO users (user_id, coins) VALUES (?, ?)", (user_id, earned_coins))
        total_coins = earned_coins
    else:
        total_coins = row[0] + earned_coins
        c.execute("UPDATE users SET coins = ? WHERE user_id = ?", (total_coins, user_id))

    conn.commit()
    conn.close()

    # Bot user ko telegram par message bhej kar batayega
    send_msg(user_id, f"🎉 *Snake Game Reward!*\nAapne is game me *+{earned_coins} Coins* earn kiye!\n🪙 Total Wallet Balance: *{total_coins} Coins*.")

    return jsonify({"status": "success", "total_coins": total_coins})

if __name__ == "__main__":
    t = threading.Thread(target=poll_telegram, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
        
