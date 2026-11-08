import sqlite3
import threading
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# 1. Apna Bot Token yahan quotes ke andar paste karein
BOT_TOKEN = "9244266282:AAHgdY5lTEoVudeisRtWL9mBrakQgXpuWF8"

# 2. Apni Blogger website ka link yahan daalein
BLOGGER_GAME_URL = "https://snakegameforplay.blogspot.com"

# 3. Wo 3 videos jo 100 coins par unlock honge
REWARD_VIDEOS = [
    "https://t.me/your_channel/1",
    "https://t.me/your_channel/2",
    "https://t.me/your_channel/3"
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    referrer_id = int(args[0]) if args and args[0].isdigit() else None

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
            try:
                await context.bot.send_message(
                    chat_id=referrer_id, 
                    text="🎉 Aapke referral se ek dost ne join kiya! Aapko +25 bonus coins mile."
                )
            except Exception:
                pass
        coins, unlocked = 0, 0
    else:
        coins, unlocked = row[1], row[2]
    conn.close()

    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    play_url = f"{BLOGGER_GAME_URL}?uid={user_id}"

    keyboard = [
        [InlineKeyboardButton("🐍 Play Snake Game & Earn Coins", url=play_url)],
        [InlineKeyboardButton("🎁 Share Referral Link (+25 Coins)", url=f"https://t.me/share/url?url={ref_link}&text=Play%20Snake%20Game%20and%20unlock%20exclusive%20videos!")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        f"👋 **Welcome to Snake Reward Bot!**\n\n"
        f"🪙 **Aapke Coins:** {coins}\n"
        f"🔓 **Unlocked Videos:** {unlocked}/3\n\n"
        f"🎯 **Rules:**\n"
        f"• Game khel kar **100 Coins / Length** banayein.\n"
        f"• 100 coins hote hi aapke **3 Videos** automatically unlock ho jayenge!\n\n"
        f"🔗 **Aapka Referral Link:**\n`{ref_link}`"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

app = Flask(__name__)
bot_app = None

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

    if trigger_unlock and bot_app:
        async def send_rewards():
            try:
                await bot_app.bot.send_message(
                    chat_id=user_id,
                    text="🎉 **Badhaai ho!** Aapne game me 100 coins complete kar liye hain!\n\n🔓 **Yahan aapke 3 Unlocked Videos hain:**"
                )
                for i, vid in enumerate(REWARD_VIDEOS, 1):
                    await bot_app.bot.send_message(
                        chat_id=user_id,
                        text=f"📹 **Video {i}:**\n{vid}"
                    )
            except Exception as e:
                print(f"Error sending reward: {e}")

        bot_app.create_task(send_rewards())

    return jsonify({"status": "success", "unlocked": trigger_unlock})

def run_flask():
    app.run(host="0.0.0.0", port=10000)

def main():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot_app.run_polling()

if __name__ == "__main__":
    main()
  
